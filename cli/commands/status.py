"""Status command - Check backend and index status."""

import asyncio
import typer
from typing import Optional

from cli.api.client import get_client, APIError
from cli.config import get_config

app = typer.Typer(help="Check status")


def status(
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL"),
    detailed: bool = typer.Option(False, "--detailed", "-d", help="Show detailed health")
):
    """Check backend health and index status."""
    async def _status():
        config = get_config()
        url = backend_url or config.backend_url

        async with get_client() as client:
            try:
                # Health check
                typer.echo(f"Backend: {url}")
                if detailed:
                    health = await client.health_detailed()
                    typer.echo(f"Status: {health.get('status', 'unknown')}")
                    details = health.get('details', {})
                    for key, value in details.items():
                        typer.echo(f"  {key}: {value}")
                else:
                    health = await client.health()
                    typer.echo(f"Status: {health.get('status', 'unknown')}")

                # Index status
                index_status = await client.get_status()
                typer.echo(f"\nIndex Status:")
                typer.echo(f"  Namespaces: {len(index_status.get('namespaces', {}))}")

                for ns, info in index_status.get('namespaces', {}).items():
                    typer.echo(f"    {ns}:")
                    typer.echo(f"      Documents: {info.get('document_count', 0)}")
                    typer.echo(f"      Chunks: {info.get('chunk_count', 0)}")

                # Recent jobs
                jobs = await client.list_jobs(limit=5)
                recent_jobs = jobs.get('jobs', [])
                if recent_jobs:
                    typer.echo(f"\nRecent Jobs:")
                    for job in recent_jobs:
                        status_icon = {
                            "pending": "⏳",
                            "processing": "🔄",
                            "completed": "✓",
                            "failed": "✗"
                        }.get(job.get('status', '?'), '?')
                        typer.echo(f"  {status_icon} {job.get('job_id')[:8]}... - {job.get('status')}")
                        if job.get('file'):
                            typer.echo(f"      File: {job.get('file')}")

            except APIError as e:
                typer.echo(f"Error: {e.message}", err=True)
                raise typer.Exit(1)

    asyncio.run(_status())
