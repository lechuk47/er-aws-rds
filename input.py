from collections.abc import Sequence
from typing import Any, Optional

from external_resources_io.input import AppInterfaceProvision
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)


class EventNotification(BaseModel):
    destination: str = Field(..., alias="destination")
    source_type: Optional[str] = Field(default="all", alias="source_type")
    event_categories: Optional[list[str]] = Field(..., alias="event_categories")


class DataClassification(BaseModel):
    loss_impact: Optional[str] = Field(..., alias="loss_impact")


class VaultSecret(BaseModel):
    path: str
    field: str
    version: Optional[int] = 1
    q_format: Optional[str] = Field(default=None)

    def to_vault_ref(self) -> str:
        json = self.model_dump_json()
        return "__vault__:" + json


class Parameter(BaseModel):
    name: str
    value: str
    apply_method: str  # Literal['immediate', 'pending-reboot'] = "immediate"

    @field_validator("value", mode="before")
    @classmethod
    def transform(cls, v: int | str | float | bool) -> str:
        """values come as int|str|float|bool from App-Interface, but terraform only allows str"""
        return str(v)


class ParameterGroup(BaseModel):
    family: str
    name: Optional[str] = None
    description: Optional[str] = None
    parameters: Optional[list[Parameter]] = Field(default=None, exclude=True)

    # This was used to populate DbParameterGroup(self, **pg.model_dump()) directy
    # but it did not work. "parameters" come from App-Interface but terraform needs "parameter" (singular)
    # @computed_field
    # def parameter(self) -> list[Parameter] | None:
    #     if self.parameters:
    #         return self.parameters
    #     return None

    # @computed_field
    # def id_(self) -> str:
    #     return self.name or ""


class ReplicaSource(BaseModel):
    region: str
    identifier: str


class RdsAppInterface(BaseModel):
    """Class with Input parameters from App-Interface that are not part of the
    Terraform aws_db_instance object.

    """

    # Name is deprecated. db_name is included as a computed_field
    name: Optional[str] = Field(
        max_length=63, pattern=r"^[a-zA-Z][a-zA-Z0-9_]+$", exclude=True
    )
    aws_partition: Optional[str] = Field(default="aws", exclude=True)
    region: str = Field(exclude=True)
    parameter_group: Optional[ParameterGroup] = Field(default=None, exclude=True)
    old_parameter_group: Optional[ParameterGroup] = Field(default=None, exclude=True)
    replica_source: Optional[ReplicaSource] = Field(default=None, exclude=True)
    enhanced_monitoring: Optional[bool] = Field(default=None, exclude=True)
    reset_password: Optional[str] = Field(default=None, exclude=True)
    ca_cert: Optional[VaultSecret] = Field(default=None, exclude=True)
    annotations: Optional[str] = Field(default=None, exclude=True)
    event_notifications: Optional[list[EventNotification]] = Field(
        default=None, exclude=True
    )
    data_classification: Optional[DataClassification] = Field(
        default=None, exclude=True
    )
    output_resource_db_name: Optional[str] = Field(default=None, exclude=True)
    # Output_resource_name is redundant
    output_resource_name: Optional[str] = Field(default=None, exclude=True)
    output_prefix: str = Field(exclude=True)
    default_tags: Sequence[dict[str, Any]] = Field(default=None, exclude=True)


class Rds(RdsAppInterface):
    """Class with input parameters from App-Interface that are part
    of the Terraform aws_db_instance object. Generally speaking, these
    parameters come from the rds defaults attributes.

    The class only defines the parameters that are changed or tweaked in the module, other
    attributes are included as extra_attributes.
    """

    model_config = ConfigDict(extra="allow")
    identifier: str
    engine: str | None = None
    allow_major_version_upgrade: Optional[bool] = False
    availability_zone: Optional[str] = None
    monitoring_interval: Optional[int] = 0
    apply_immediately: Optional[bool] = False
    multi_az: Optional[bool] = False
    replicate_source_db: Optional[str] = None
    snapshot_identifier: Optional[str] = None
    backup_retention_period: Optional[int] = None
    db_subnet_group_name: Optional[str] = None
    storage_encrypted: Optional[bool] = None
    kms_key_id: Optional[str] = None
    username: Optional[str] = None
    # _password is not in the input, the field is used to populate the random password
    password: Optional[str] = None
    parameter_group_name: Optional[str] = None
    tags: dict[str, Any]

    @computed_field
    def id_(self) -> str:
        return self.identifier

    @computed_field
    def db_name(self) -> str | None:
        return self.name

    def is_replica_or_from_snapshot(self) -> bool:
        if self.replica_source or self.replicate_source_db or self.snapshot_identifier:
            return True
        return False

    @model_validator(mode="after")
    def az_belongs_to_region(self) -> "Rds":
        if self.availability_zone:
            az_region = self.availability_zone[:-1]
            if self.region != az_region:
                raise ValueError(
                    "Availabilizy_zone does not belong to region",
                    self.availability_zone,
                    self.region,
                )
        return self

    @model_validator(mode="after")
    def unset_az_if_multi_region(self) -> "Rds":
        if self.multi_az:
            self.availability_zone = None
        return self

    @model_validator(mode="after")
    def unset_replica_or_snapshot_not_allowed_attrs(self) -> "Rds":
        if self.is_replica_or_from_snapshot():
            self.username = None
            self.password = None
            self.name = None
            self.engine = None
            self.allocated_storage = None
        return self

    @model_validator(mode="after")
    def replication(self) -> "Rds":
        if self.replica_source and self.replicate_source_db:
            raise ValueError(
                "Only one of replicate_source_db or replica_source can be defined"
            )
        elif self.replica_source and self.replica_source.region != self.region:
            # CROSS-REGION Replication
            if not self.db_subnet_group_name:
                raise ValueError(
                    "db_subnet_group_name must be defined for cross-region replicas"
                )
            elif self.storage_encrypted and not self.kms_key_id:
                raise ValueError(
                    "storage_encrypted ignored for cross-region read replica. Set kms_key_id"
                )
        return self

    @model_validator(mode="after")
    def parameter_groups(self) -> "Rds":
        if self.old_parameter_group and not self.parameter_group:
            raise ValueError(
                "old_parameter_group must be used with parameter_group. "
                "old_parameter_group is only ysed for RDS major version upgrades"
            )
        elif self.old_parameter_group and self.parameter_group:
            default_pg_name = self.identifier + "-pg"
            self.parameter_group.name = self.parameter_group.name or default_pg_name
            self.old_parameter_group.name = (
                self.old_parameter_group.name or default_pg_name
            )
            if self.old_parameter_group.name == self.parameter_group.name:
                raise ValueError("parameter_group must have a unique name")
        return self


class AppInterfaceInput(BaseModel):
    data: Rds
    provision: AppInterfaceProvision
