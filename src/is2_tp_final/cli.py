"""Console script for is2_tp_final."""

import typer
from rich.console import Console

from is2_tp_final import utils

app = typer.Typer()
console = Console()


@app.command()
def main() -> None:
    """Console script for is2_tp_final."""
    console.print("Replace this message by putting your code into is2_tp_final.cli.main")
    console.print("See Typer documentation at https://typer.tiangolo.com/")
    utils.do_something_useful()


if __name__ == "__main__":
    app()
