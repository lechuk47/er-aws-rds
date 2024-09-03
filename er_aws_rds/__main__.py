from cdktf import App
from external_resources_io.input import parse_model, read_input_from_file

from er_aws_rds.input import AppInterfaceInput
from er_aws_rds.rds import Stack

app_interface_input: AppInterfaceInput = parse_model(
    AppInterfaceInput, read_input_from_file()
)
app = App()
Stack(app, "CDKTF", app_interface_input)
app.synth()
