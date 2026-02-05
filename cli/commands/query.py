"""Query command - Search the vector store."""

import asyncio
import json
import typer
from typing import Optional

from cli.api.client import get_client, APIError
from cli.config import get_config

app = typer.Typer(help="Query the vector store")


def query(
    query_text: str = typer.Argument(..., help="Search query"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Namespace to search"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of results"),
    filter_json: Optional[str] = typer.Option(None, "--filter", "-f", help="Filter as JSON string"),
    output: str = typer.Option("table", "--output", "-o", help="Output format: table, json"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """Search the vector store for similar content."""
    async def _query():
        config = get_config()
        url = backend_url or config.backend_url

        # Parse filter if provided
        filter_dict = None
        if filter_json:
            try:
                filter_dict = json.loads(filter_json)
            except json.JSONDecodeError:
                typer.echo(f"Error: Invalid JSON in filter", err=True)
                raise typer.Exit(1)

        async with get_client() as client:
            try:
                result = await client.query(
                    query=query_text,
                    namespace=namespace,
                    top_k=top_k,
                    filter=filter_dict
                )

                if output == "json":
                    typer.echo(json.dumps(result, indent=2))
                else:
                    # Table output
                    results = result.get("results", [])
                    if not results:
                        typer.echo("No results found.")
                        return

                    typer.echo(f"\nQuery: {query_text}")
                    typer.echo(f"Found {len(results)} results:\n")

                    for i, r in enumerate(results, 1):
                        typer.echo(f"{i}. [{r.get('filename', 'N/A')}]")
                        typer.echo(f"   Score: {r.get('score', 0):.3f}")
                        content = r.get('content', '')
                        if len(content) > 200:
                            content = content[:200] + "..."
                        typer.echo(f"   Content: {content}\n")

            except APIError as e:
                typer.echo(f"Error: {e.message}", err=True)
                raise typer.Exit(1)

    asyncio.run(_query())
