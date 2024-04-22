import json

from cdktf import Testing
from input import AppInterfaceInput

Testing.__test__ = False


def input_data() -> dict:
    return json.loads("""{
        "data": {
            "engine": "postgres",
            "engine_version": "14.6",
            "name": "postgres",
            "username": "postgres",
            "instance_class": "db.t3.micro",
            "allocated_storage": 20,
            "auto_minor_version_upgrade": false,
            "skip_final_snapshot": true,
            "backup_retention_period": 7,
            "storage_type": "gp2",
            "multi_az": false,
            "ca_cert_identifier": "rds-ca-rsa2048-g1",
            "publicly_accessible": true,
            "apply_immediately": true,
            "identifier": "test-rds",
            "parameter_group": {
                "name": "postgres-14",
                "family": "postgres14",
                "description": "Parameter Group for PostgreSQL 14",
                "parameters": [
                    {
                        "name": "log_statement",
                        "value": "none",
                        "apply_method": "pending-reboot"
                    },
                    {
                        "name": "log_min_duration_statement",
                        "value": -1,
                        "apply_method": "pending-reboot"
                    }
                ]
            },
            "output_resource_name": "test-rds-credentials",
            "ca_cert": {
                "path": "app-interface/global/rds-ca-cert",
                "field": "us-east-1",
                "version": 2,
                "q_format": null
            },
            "output_prefix": "prefixed-test-rds",
            "region": "us-east-1"
        },
        "provision": {
            "provision_provider": "aws",
            "provisioner": "app-int-example-01",
            "provider": "rds",
            "identifier": "test-rds",
            "target_cluster": "appint-ex-01",
            "target_namespace": "external-resources-poc",
            "target_secret_name": "test-rds-credentials",
            "module_provision_data": {
                "tf_state_bucket": "external-resources-terraform-state-dev",
                "tf_state_region": "us-east-1",
                "tf_state_dynamodb_table": "external-resources-terraform-lock",
                "tf_state_key": "aws/app-int-example-01/rds/test-rds/terraform.tfstate"
            }
        }
    }
    """)


def input_object() -> AppInterfaceInput:
    return AppInterfaceInput.model_validate(input_data())
