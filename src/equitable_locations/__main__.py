import click


@click.command()
def initialize_censusdata():
    # Code to initialize censusdata goes here
    click.echo("Censusdata initialized successfully!")


@click.command()
def initialize_isochrone_data():
    # Code to initialize isochrone data goes here
    click.echo("Isochrone data initialized successfully!")


@click.command()
def say_hello():
    click.echo("Hello, World!")


@click.group()
def cli():
    pass


cli.add_command(initialize_censusdata)
cli.add_command(initialize_isochrone_data)
cli.add_command(say_hello)

if __name__ == "__main__":
    cli(program_name="equitable_locations")
