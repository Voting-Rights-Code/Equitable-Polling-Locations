import click
from equitable_locations.io.model_config import PollingModelConfig
from equitable_locations.optimization.run_models import run_model


@click.command()
@click.argument("file_path", type=click.Path(exists=True))
def run_file(file_path):
    # Code to run optimization on a single config file
    click.echo(f"Running config on {file_path}")
    config = PollingModelConfig.load_config_file(file_path)
    run_model(config)


@click.command()
def run_directory():
    # Code to initialize isochrone data goes here
    click.echo("Running directory of configs!")
    raise NotImplementedError


@click.command()
def say_hello():
    click.echo("Hello, World!")


@click.group()
def cli():
    pass


cli.add_command(run_file)
cli.add_command(run_directory)
cli.add_command(say_hello)

if __name__ == "__main__":
    cli()
