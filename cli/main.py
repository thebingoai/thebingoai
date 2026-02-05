#!/usr/bin/env python3
"""Typer CLI entry point for LLM Markdown CLI."""

import asyncio
import typer
from pathlib import Path
from typing import Optional

from cli.config import get_config, save_config, set_config_value, Config
from cli.api.client import BackendClient, APIError, get_client
from cli.commands.upload import upload
from cli.commands.query import query
from cli.commands.chat import chat
from cli.commands.status import status

app = typer.Typer(help="LLM Markdown CLI - Search and chat with your markdown files")

# Register sub-commands
app.command()(upload)
app.command()(query)
app.command()(chat)
app.command()(status)


@app.command()
def configure(
    key: str = typer.Argument(..., help="Config key (backend_url, webhook_url, default_provider, default_namespace)"),
    value: str = typer.Argument(..., help="Config value")
):
    """Set a configuration value."""
    try:
        set_config_value(key, value)
        typer.echo(f"✓ Set {key} = {value}")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def config_show():
    """Show current configuration."""
    config = get_config()
    typer.echo("Current configuration:")
    typer.echo(f"  backend_url: {config.backend_url}")
    typer.echo(f"  webhook_url: {config.webhook_url or '(none)'}")
    typer.echo(f"  default_provider: {config.default_provider}")
    typer.echo(f"  default_namespace: {config.default_namespace}")


@app.callback()
def main(
    ctx: typer.Context,
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output")
):
    """LLM Markdown CLI - Search and chat with your markdown files."""
    ctx.ensure_object(dict)
    ctx.obj["backend_url"] = backend_url
    ctx.obj["verbose"] = verbose


if __name__ == "__main__":
    app()
