"""Upload command - Upload markdown files to the vector store."""

import asyncio
import typer
from pathlib import Path
from typing import Optional, List

from cli.api.client import get_client, APIError
from cli.config import get_config

app = typer.Typer(help="Upload markdown files")


def upload(
    file: Path = typer.Argument(..., exists=True, help="Path to markdown file to upload"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Namespace for the file"),
    tags: List[str] = typer.Option([], "--tag", "-t", help="Tags for the file"),
    webhook_url: Optional[str] = typer.Option(None, "--webhook", "-w", help="Webhook URL for async completion"),
    force_async: bool = typer.Option(False, "--async", "-a", help="Force async processing"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """Upload a markdown file to the vector store."""
    async def _upload():
        config = get_config()
        url = backend_url or config.backend_url

        typer.echo(f"Uploading {file.name}...")

        async with get_client() as client:
            try:
                result = await client.upload_file(
                    file_path=file,
                    namespace=namespace,
                    tags=tags,
                    webhook_url=webhook_url,
                    force_async=force_async
                )

                if result.get("async"):
                    job_id = result.get("job_id")
                    typer.echo(f"✓ File queued for async processing")
                    typer.echo(f"  Job ID: {job_id}")
                    typer.echo(f"  Namespace: {namespace}")
                else:
                    typer.echo(f"✓ File uploaded and indexed")
                    typer.echo(f"  File: {result.get('filename')}")
                    typer.echo(f"  Chunks: {result.get('chunk_count')}")
                    typer.echo(f"  Namespace: {namespace}")

            except APIError as e:
                typer.echo(f"Error: {e.message}", err=True)
                raise typer.Exit(1)

    asyncio.run(_upload())
