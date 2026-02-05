"""Chat command - Interactive RAG chat."""

import asyncio
import typer
from typing import Optional

from cli.api.client import get_client, APIError
from cli.config import get_config

app = typer.Typer(help="Chat with RAG")


def chat(
    question: str = typer.Argument(..., help="Your question"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Namespace to search"),
    provider: str = typer.Option("openai", "--provider", "-p", help="LLM provider"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name"),
    temperature: float = typer.Option(0.7, "--temperature", "-t", help="Temperature (0.0-1.0)"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of context chunks"),
    thread_id: Optional[str] = typer.Option(None, "--thread", help="Conversation thread ID"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream response"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """Ask a question using RAG (Retrieval-Augmented Generation)."""
    async def _chat():
        config = get_config()
        url = backend_url or config.backend_url

        async with get_client() as client:
            try:
                if stream:
                    # Streaming response
                    async for chunk in client.ask_stream(
                        question=question,
                        namespace=namespace,
                        top_k=top_k,
                        provider=provider,
                        model=model,
                        temperature=temperature,
                        thread_id=thread_id
                    ):
                        chunk_type = chunk.get("type", "")

                        if chunk_type == "context":
                            # Show retrieved context
                            context = chunk.get("context", [])
                            typer.echo(f"\n📚 Retrieved {len(context)} chunks:\n")
                            for i, c in enumerate(context, 1):
                                typer.echo(f"  [{i}] {c.get('filename', 'N/A')} (score: {c.get('score', 0):.2f})")

                        elif chunk_type == "thread_id":
                            thread_id = chunk.get("thread_id")
                            typer.echo(f"\n🧵 Thread: {thread_id}\n")

                        elif chunk_type == "content":
                            # Stream content
                            content = chunk.get("content", "")
                            typer.echo(content, nl=False)

                        elif chunk_type == "done":
                            typer.echo()  # New line after streaming
                            usage = chunk.get("usage", {})
                            if usage:
                                typer.echo(f"\nTokens: {usage.get('total_tokens', 0)}")
                else:
                    # Non-streaming response
                    result = await client.ask(
                        question=question,
                        namespace=namespace,
                        top_k=top_k,
                        provider=provider,
                        model=model,
                        temperature=temperature,
                        thread_id=thread_id
                    )

                    # Show context
                    context = result.get("context", [])
                    typer.echo(f"📚 Retrieved {len(context)} chunks:\n")
                    for i, c in enumerate(context, 1):
                        typer.echo(f"  [{i}] {c.get('filename', 'N/A')} (score: {c.get('score', 0):.2f})")

                    # Show thread
                    thread_id = result.get("thread_id")
                    if thread_id:
                        typer.echo(f"\n🧵 Thread: {thread_id}\n")

                    # Show answer
                    answer = result.get("answer", "")
                    typer.echo(f"{answer}\n")

                    # Show usage
                    usage = result.get("usage", {})
                    if usage:
                        typer.echo(f"Tokens: {usage.get('total_tokens', 0)}")

            except APIError as e:
                typer.echo(f"Error: {e.message}", err=True)
                raise typer.Exit(1)

    asyncio.run(_chat())
