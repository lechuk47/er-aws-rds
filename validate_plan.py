import sys
from collections.abc import Mapping
from typing import Any

from boto3 import Session
from botocore.config import Config
from external_resources_io.input import parse_model, read_input_from_file
from external_resources_io.terraform import (
    Action,
    ResourceChange,
    TerraformJsonPlanParser,
)
from mypy_boto3_rds import RDSClient
from mypy_boto3_rds.type_defs import FilterTypeDef

from input import AppInterfaceInput


class AWSApi:
    def __init__(self, config_options: Mapping[str, Any]) -> None:
        self.session = Session()
        self.config = Config(**config_options)

    def get_rds_client(self) -> RDSClient:
        return self.session.client("rds", config=self.config)

    def get_rds_valid_update_versions(self, engine: str, version: str) -> set[str]:
        data = self.get_rds_client().describe_db_engine_versions(
            Engine=engine, EngineVersion=version, IncludeAll=True
        )

        if data["DBEngineVersions"] and len(data["DBEngineVersions"]) == 1:
            return {
                item.get("EngineVersion", "-1")
                for item in data["DBEngineVersions"][0].get("ValidUpgradeTarget", [])
            }
        else:
            return set[str]()

    def get_rds_parameter_groups(self, engine: str) -> set[str]:
        filters: list[FilterTypeDef] = [
            {"Name": "db-parameter-group-family", "Values": [engine]},
        ]
        resp = self.get_rds_client().describe_db_parameter_groups(Filters=filters)
        return {group["DBParameterGroupName"] for group in resp["DBParameterGroups"]}


class RDSPlanValidator:
    def __init__(self, plan: TerraformJsonPlanParser, input: AppInterfaceInput) -> None:
        self.plan = plan
        self.input = input
        self.aws_api = AWSApi(config_options={"region_name": "us-east-1"})
        self.errors: list[str] = []

    @property
    def aws_db_instance_updates(self) -> list[ResourceChange]:
        return [
            c
            for c in self.plan.plan.resource_changes
            if c.type == "aws_db_instance"
            and c.change
            and Action.ActionUpdate in c.change.actions
        ]

    def _validate_major_version_upgrade(self) -> None:
        for u in self.aws_db_instance_updates:
            if not u.change:
                continue
            current_version = u.change.before["engine_version"]
            desired_version = u.change.after["engine_version"]
            if current_version != desired_version:
                valid_update_versions = self.aws_api.get_rds_valid_update_versions(
                    u.change.before["engine"], current_version
                )
                if desired_version not in valid_update_versions:
                    self.errors.append(
                        "Engine version cannot be updated. Current_version: %s, Desired_version: %s, Valid update versions: %s"
                        % (current_version, desired_version, valid_update_versions)
                    )
                if not self.input.data.allow_major_version_upgrade:
                    self.errors.append(
                        "To enable major version ugprades, allow_major_version_ugprade attribute must be set to True"
                    )

    def validate(self) -> bool:
        self._validate_major_version_upgrade()
        if self.errors:
            return False
        else:
            return True


if __name__ == "__main__":
    input: AppInterfaceInput = parse_model(
        AppInterfaceInput,
        read_input_from_file(),
    )
    print("Running RDS terraform plan validation:")
    plan = TerraformJsonPlanParser(plan_path=sys.argv[1])
    validator = RDSPlanValidator(plan, input)
    if not validator.validate():
        print(validator.errors)
        sys.exit(1)
    else:
        sys.exit(0)
