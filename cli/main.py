#!/usr/bin/env python3
"""Typer CLI entry point for LLM Markdown CLI."""

import asyncio
import typer
from pathlib import Path
from typing import Optional

from cli.config import get_config, save_config, set_config_value, Config
from cli.api.client import BackendClient, APIError, get_client
from cli.commands import upload, query, chat, status, index
from cli.cache.index_cache import clear_cache

app = typer.Typer(
    help="LLM Markdown CLI - Search and chat with your markdown files",
    no_args_is_help=True
)

# Register sub-commands as groups
app.add_typer(upload.app, name="upload", help="Upload markdown files")
app.add_typer(index.app, name="index", help="Manage indexed folders")

# Register individual commands
app.command()(query.query)
app.command()(chat.chat)
app.command()(status.status)


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


@app.command(hidden=True)
def ask(
    question: str = typer.Argument(..., help="Your question with optional @folder reference"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Namespace to search"),
    provider: str = typer.Option("openai", "--provider", "-p", help="LLM provider"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of context chunks"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream response")
):
    """Ask a question (use 'chat' command instead)."""
    typer.echo("Use 'mdcli chat' for asking questions.")
    raise typer.Exit(1)


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
