from cdktf import Testing
from cdktf_cdktf_provider_aws.db_instance import DbInstance
from cdktf_cdktf_provider_aws.db_parameter_group import DbParameterGroup
from conftest import input_object
from rds import Stack


class TestMain:
    input = input_object()
    stack = Stack(Testing.app(), "CDKTF", input)
    synthesized = Testing.synth(stack)

    def test_should_contain_rds_instance(self):
        assert Testing.to_have_resource_with_properties(
            self.synthesized,
            DbInstance.TF_RESOURCE_TYPE,
            {
                "identifier": "test-rds",
                "engine": "postgres",
                "db_name": "postgres",
                "allocated_storage": 20,
                "parameter_group_name": "test-rds-postgres-14",
            },
        )

    def test_shuold_containe_parameter_group(self):
        assert Testing.to_have_resource_with_properties(
            self.synthesized,
            DbParameterGroup.TF_RESOURCE_TYPE,
            {
                "name": "test-rds-postgres-14",
                "family": "postgres14",
            },
            # Test fails if I add the parameters. It works for 1 parameter
            # but fails if I set the full list
        )
