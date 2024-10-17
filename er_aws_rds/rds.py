import json
from typing import ClassVar

from cdktf import (
    ITerraformDependable,
    Precondition,
    S3Backend,
    TerraformOutput,
    TerraformResourceLifecycle,
    TerraformStack,
)
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

from er_aws_rds.input import AppInterfaceInput, ParameterGroup


class Stack(TerraformStack):
    "AWS RDS Stack"

    db_dependencies: ClassVar[list[ITerraformDependable]] = []

    def __init__(
        self, scope: Construct, id_: str, app_interface_input: AppInterfaceInput
    ) -> None:
        super().__init__(scope, id_)
        self.data = app_interface_input.data
        self.provision = app_interface_input.provision
        self._init_providers()
        self._run()

    def _init_providers(self) -> None:
        S3Backend(
            self,
            bucket=self.provision.module_provision_data.tf_state_bucket,
            key=self.provision.module_provision_data.tf_state_key,
            encrypt=True,
            region=self.provision.module_provision_data.tf_state_region,
            dynamodb_table=self.provision.module_provision_data.tf_state_dynamodb_table,
            profile="external-resources-state",
        )
        AwsProvider(
            self,
            "Aws",
            region=self.data.region,
            default_tags=self.data.default_tags,
        )
        RandomProvider(self, "Random")

    def _populate_parameter_group(
        self, pg: ParameterGroup, db_identifier: str, tags: dict[str, str]
    ) -> str:
        # Dumping the whole parameter group doesn't work. "Parameter" values are populated correctly
        # but CDKTF does not take the apply_method attribute.
        # I don't know/understand why. Dumping the parameters separately works well.
        # DbParameterGroup(self, **pg.model_dump())

        # With this model each database will have it's own PG
        # No re-use. If a common PG is changed in AppInterface, all dependant
        # database PGs will be reconciled
        pg_name = f"{db_identifier}-{pg.name or 'pg'}"

        dbpg = DbParameterGroup(
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
            lifecycle=TerraformResourceLifecycle(create_before_destroy=True),
        )

        self.db_dependencies.append(dbpg)
        return pg_name

    def _parameter_groups(self) -> None:
        """Creates required parameter groups"""
        if self.data.parameter_group:
            self.data.parameter_group_name = self._populate_parameter_group(
                self.data.parameter_group,
                self.data.identifier,
                self.data.tags,
            )

        if self.data.old_parameter_group:
            self._populate_parameter_group(
                self.data.old_parameter_group,
                self.data.identifier,
                self.data.tags,
            )

    def _password(self) -> None:
        self.data.password = Password(
            self,
            id=f"{self.data.identifier}-password",
            length=20,
            min_special=0,  # need to be 0 to import current password. It should be improved in next version of module once the instaces are imported.
            min_numeric=0,
            keepers={"reset_password": self.data.reset_password or ""},
        ).result

    def _enhanced_monitoring(self) -> None:
        if self.data.enhanced_monitoring:
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
                id_=self.data.identifier + "-enhanced-monitoring",
                assume_role_policy=json.dumps(assume_role_policy),
            )

            policy_arn = f"arn:{self.data.aws_partition}:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
            IamRolePolicyAttachment(
                self,
                id_=f"{self.data.identifier}-policy-attachment",
                role=m_role.name,
                policy_arn=policy_arn,
            )

    def _db_replicas(self) -> None:
        if self.data.replica_source:
            self.data.backup_retention_period = 0
            source_db_identifier = self.data.replica_source.identifier
            source_db_region = self.data.replica_source.region

            if self.data.region != self.data.replica_source.region:
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
                self.data.replicate_source_db = source_db.db_instance_arn
            else:
                source_db = DataAwsDbInstance(
                    self,
                    id_=f"data-{source_db_identifier}",
                    db_instance_identifier=source_db_identifier,
                )
                self.data.replicate_source_db = source_db.db_instance_identifier
                self.data.db_subnet_group_name = (
                    None  # Only needs to be set for cross-region replicas
                )

    def _kms_key(self) -> None:
        if self.data.kms_key_id and not self.data.kms_key_id.startswith("arn:"):
            data_kms = DataAwsKmsKey(
                self, id_="data-kms", key_id=f"{self.data.kms_key_id}"
            )
            self.data.kms_key_id = data_kms.arn

    def _db_instance(self) -> DbInstance:
        return DbInstance(
            self,
            **self.data.model_dump(exclude_none=True),
            depends_on=self.db_dependencies,
        )

    def _event_notifications(self, db_instance: DbInstance) -> None:
        # Event Notifications
        for en in self.data.event_notifications or []:
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

    def _outputs(self, db_instance: DbInstance) -> None:
        TerraformOutput(
            self,
            "BLABLABLAB",
            value="TRUE",
            precondition=Precondition(
                condition=db_instance.allow_major_version_upgrade, error_message="ERROR"
            ),
        )
        TerraformOutput(
            self, self.data.output_prefix + "__db_host", value=db_instance.address
        )
        TerraformOutput(
            self, self.data.output_prefix + "__db_port", value=db_instance.port
        )
        TerraformOutput(
            self,
            self.data.output_prefix + "__db_name",
            value=self.data.output_resource_db_name or db_instance.db_name,
        )

        if self.data.ca_cert:
            TerraformOutput(
                self,
                self.data.output_prefix + "__db_ca_cert",
                sensitive=False,
                value=self.data.ca_cert.to_vault_ref(),
            )

        if not (
            self.data.replica_source
            or self.data.replicate_source_db
            or self.data.snapshot_identifier
        ):
            TerraformOutput(
                self,
                self.data.output_prefix + "__db_user",
                value=db_instance.username,
                sensitive=True,
            )
            TerraformOutput(
                self,
                self.data.output_prefix + "__db_password",
                value=db_instance.password,
                sensitive=True,
            )
            if self.data.reset_password:
                TerraformOutput(
                    self,
                    self.data.output_prefix + "__reset_password",
                    value=self.data.reset_password,
                )

    def _run(self) -> None:
        self._password()
        self._parameter_groups()
        self._enhanced_monitoring()
        self._db_replicas()
        self._kms_key()
        db_instance = self._db_instance()
        self._event_notifications(db_instance)
        self._outputs(db_instance)
