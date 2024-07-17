from cdktf import App
from external_resources_io.input import parse_model, read_input_from_file

from input import AppInterfaceInput
from rds import Stack

input: AppInterfaceInput = parse_model(AppInterfaceInput, read_input_from_file())
app = App()
Stack(app, "CDKTF", input)
app.synth()
