#!/usr/bin/env python
import json

from cdktf import S3Backend, TerraformOutput, TerraformStack
from cdktf_cdktf_provider_aws.data_aws_db_instance import DataAwsDbInstance
from cdktf_cdktf_provider_aws.data_aws_kms_key import DataAwsKmsKey
from cdktf_cdktf_provider_aws.data_aws_sns_topic import DataAwsSnsTopic
from cdktf_cdktf_provider_aws.db_event_subscription import DbEventSubscription
from cdktf_cdktf_provider_aws.db_instance import DbInstance
from cdktf_cdktf_provider_aws.db_parameter_group import (
    DbParameterGroup,
    DbParameterGroupParameter,
)
from cdktf_cdktf_provider_aws.iam_role import IamRole
from cdktf_cdktf_provider_aws.iam_role_policy_attachment import IamRolePolicyAttachment
from cdktf_cdktf_provider_aws.provider import AwsProvider
from cdktf_cdktf_provider_random.password import Password
from cdktf_cdktf_provider_random.provider import RandomProvider
from constructs import Construct

# from external_resources_io.input import parse_base64_model
from input import AppInterfaceInput, ParameterGroup  # , clean_data

# 1.- Check rds name is empty or under 63 chars
# 2.- Apply immediate default to False if not set (Module)
# 3.- Multi_AZ Checks
# If multi-az -> pop availability_zone --> IF multi-az and availability_zone throw error ?¿
# If multi-region-account:
#  - if AZ -> provider from REGION_FROM_(AZ)
#  - if REGION ->
# if AZ -> check AZ belongs to REGION
# if no AZ -> provider from REGION
# Parameter Group.
#  If parameter_group populate_pg
#  If old_parameter_group.
#    If no parameter_group -> ERROR
#    If pg_name == old_pg_name -> ERROR
# Enhanced monitoring
# If enhanced_monitoring (POP)
#   monitoring_interval = 60 if not set
#  Create IAM Role for enhanced monitoring
#  Attach AmazonRDSEnhancedMonitoringRole to the Role
# RESET PASSWORD
# CA_CERT
# REPLICA_SOURCE (Gets the other instance from AppInterface)
# backup_retention_period=0
# replica_region == region
#
# replica_region != region
# KMS_KEY
# EVENT NOTIFICATIONS
# OUTPUTS


class Stack(TerraformStack):
    def _populate_parameter_group(
        self, pg: ParameterGroup, db_identifier: str, tags: dict[str, str]
    ) -> str:
        # Dumping the whole parameter group doesn't work. "Parameter" values are populated correctly
        # but CDKTF does not take the apply_method attribute.
        # I don't know/understand why. Dumping the parameters separately works well.
        # DbParameterGroup(self, **pg.model_dump())
        #

        # With this model each database will have it's own PG
        # No re-use. If a common PG is changed in AppInterface, all dependant
        # database PGs will be reconciled
        pg_name = f"{db_identifier}-{pg.name or 'pg'}"

        DbParameterGroup(
            self,
            id_=pg_name,
            name=pg_name,
            family=pg.family,
            description=pg.description,
            parameter=[
                DbParameterGroupParameter(**p.model_dump(exclude_none=True))
                for p in pg.parameters or []
            ],
            tags=tags,
        )

        return pg_name

    def __init__(self, scope: Construct, id: str, input: AppInterfaceInput):
        super().__init__(scope, id)

        module_provision_data = input.provision.module_provision_data

        S3Backend(
            self,
            bucket=module_provision_data.tf_state_bucket,
            key=module_provision_data.tf_state_key,
            encrypt=True,
            region=module_provision_data.tf_state_region,
            dynamodb_table=module_provision_data.tf_state_dynamodb_table,
            profile="external-resources-state",
        )
        AwsProvider(
            self,
            "Aws",
            region=input.data.region,
            default_tags=input.data.default_tags,
        )
        RandomProvider(self, "Random")

        input.data.password = Password(
            self,
            id=f"{input.data.identifier}-password",
            length=20,
            min_special=0,  # need to be 0 to import current password. It should be improved in next version of module once the instaces are imported.
            min_numeric=0,
            keepers={"reset_password": input.data.reset_password or ""},
        ).result

        if input.data.parameter_group:
            input.data.parameter_group_name = self._populate_parameter_group(
                input.data.parameter_group, input.data.identifier, input.data.tags
            )

        if input.data.old_parameter_group:
            self._populate_parameter_group(
                input.data.old_parameter_group, input.data.identifier, input.data.tags
            )

        if input.data.enhanced_monitoring:
            assume_role_policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Action": "sts:AssumeRole",
                        "Principal": {"Service": "monitoring.rds.amazonaws.com"},
                        "Effect": "Allow",
                    }
                ],
            }
            m_role = IamRole(
                self,
                id_=input.data.identifier + "-enhanced-monitoring",
                assume_role_policy=json.dumps(assume_role_policy),
            )

            policy_arn = f"arn:{input.data.aws_partition}:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
            IamRolePolicyAttachment(
                self,
                id_=f"{input.data.identifier}-policy-attachment",
                role=m_role.name,
                policy_arn=policy_arn,
            )

        if input.data.replica_source:
            input.data.backup_retention_period = 0
            source_db_identifier = input.data.replica_source.identifier
            source_db_region = input.data.replica_source.region

            if input.data.region != input.data.replica_source.region:
                source_db_provider = AwsProvider(
                    self,
                    f"AWS-{source_db_region}",
                    region=source_db_region,
                    alias=f"AWS-{source_db_region}",
                )
                source_db = DataAwsDbInstance(
                    self,
                    id_=f"data-{source_db_identifier}",
                    db_instance_identifier=source_db_identifier,
                    provider=source_db_provider,
                )
                input.data.replicate_source_db = source_db.db_instance_arn
            else:
                source_db = DataAwsDbInstance(
                    self,
                    id_=f"data-{source_db_identifier}",
                    db_instance_identifier=source_db_identifier,
                )
                input.data.replicate_source_db = source_db.db_instance_identifier
                input.data.db_subnet_group_name = (
                    None  # Only needs to be set for cross-region replicas
                )

        if input.data.kms_key_id:
            if not input.data.kms_key_id.startswith("arn:"):
                data_kms = DataAwsKmsKey(
                    self, id_="data-kms", key_id=f"{input.data.kms_key_id}"
                )
                input.data.kms_key_id = data_kms.arn

        db_instance = DbInstance(self, **input.data.model_dump(exclude_none=True))

        # Event Notifications
        for en in input.data.event_notifications or []:
            if en.destination.startswith("arn:"):
                sns_topic_arn = en.destination
            else:
                dsid = "data_" + en.destination
                d = DataAwsSnsTopic(self, id_=dsid, name=en.destination)
                sns_topic_arn = d.arn

            DbEventSubscription(
                self,
                id_=f"{en.destination}_{en.source_type}_event_subs",
                sns_topic=sns_topic_arn,
                source_ids=[db_instance.id],
            )

        output_prefix = input.data.output_prefix
        TerraformOutput(self, output_prefix + "__db_host", value=db_instance.address)
        TerraformOutput(self, output_prefix + "__db_port", value=db_instance.port)
        TerraformOutput(
            self,
            output_prefix + "__db_name",
            value=input.data.output_resource_db_name or db_instance.db_name,
        )

        if input.data.ca_cert:
            TerraformOutput(
                self,
                output_prefix + "__db_ca_cert",
                sensitive=False,
                value=input.data.ca_cert.to_vault_ref(),
            )

        if not input.data.is_replica_or_from_snapshot():
            TerraformOutput(
                self,
                output_prefix + "__db_user",
                value=db_instance.username,
                sensitive=True,
            )
            TerraformOutput(
                self,
                output_prefix + "__db_password",
                value=db_instance.password,
                sensitive=True,
            )
            if input.data.reset_password:
                TerraformOutput(
                    self,
                    output_prefix + "__reset_password",
                    value=input.data.reset_password,
                )
