"""Chat command with interactive TUI support."""

import asyncio
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.prompt import Confirm

from cli.config import get_config
from cli.cache.index_cache import is_folder_indexed
from cli.resolver.folder_resolver import (
    extract_folder_references,
    remove_folder_references,
    resolve_folder
)
from cli.api.client import get_client, APIError

console = Console()
app = typer.Typer(help="Chat with your indexed documents")


@app.command("interactive")
def chat_interactive(
    provider: str = typer.Option("openai", "--provider", "-p", help="LLM provider"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name"),
    folder: str = typer.Option(None, "--folder", "-f", help="Pre-load a folder context"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """
    Start interactive chat session (Claude Code-style TUI).
    
    Examples:
        mdcli chat interactive
        mdcli chat interactive --folder my-notes
        mdcli chat interactive --provider anthropic
    """
    from cli.tui.app import ChatApp
    
    config = get_config()
    url = backend_url or config.backend_url
    
    # Create and run the TUI app
    tui_app = ChatApp(
        backend_url=url,
        provider=provider,
        folder=folder
    )
    
    tui_app.run()


@app.command("ask")
def chat_ask(
    question: str = typer.Argument(..., help="Your question (can include @folder reference)"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Namespace to search"),
    provider: str = typer.Option("openai", "--provider", "-p", help="LLM provider"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model name"),
    temperature: float = typer.Option(0.7, "--temperature", "-t", help="Temperature (0.0-1.0)"),
    top_k: int = typer.Option(5, "--top-k", "-k", help="Number of context chunks"),
    thread_id: Optional[str] = typer.Option(None, "--thread", help="Conversation thread ID"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream response"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """
    Ask a single question with optional @folder reference.
    
    Examples:
        mdcli chat ask "@my-notes What are embeddings?"
        mdcli chat ask "Explain transformers" --provider anthropic
        mdcli chat ask "Summarize this" --namespace docs
    """
    async def _ask():
        config = get_config()
        url = backend_url or config.backend_url
        
        # Extract @folder reference
        folder_refs = extract_folder_references(question)
        
        target_namespace = namespace
        if folder_refs:
            if len(folder_refs) > 1:
                console.print("[red]Please use only one @folder reference.[/red]")
                raise typer.Exit(1)
            
            folder_ref = folder_refs[0]
            resolved = resolve_folder(folder_ref)
            
            if not resolved:
                console.print(f"[red]Folder '{folder_ref}' not found.[/red]")
                raise typer.Exit(1)
            
            folder_path, folder_name = resolved
            
            # Check if indexed
            if not is_folder_indexed(folder_name):
                console.print(f"📁 Folder '{folder_name}' is not indexed.")
                
                md_files = list(Path(folder_path).glob("**/*.md"))
                if md_files:
                    if Confirm.ask(f"Index {len(md_files)} files now?", default=True):
                        # Index the folder first
                        from cli.cache.index_cache import update_cache, get_file_hash
                        
                        console.print(f"[dim]Indexing {len(md_files)} files...[/dim]")
                        
                        async with get_client() as client:
                            total_chunks = 0
                            file_hashes = {}
                            
                            for file_path in md_files:
                                rel_path = str(file_path.relative_to(folder_path))
                                result = await client.upload_file(
                                    file_path=file_path,
                                    namespace=folder_name,
                                    tags=[folder_name]
                                )
                                if result.get("chunks_created"):
                                    total_chunks += result["chunks_created"]
                                file_hashes[rel_path] = get_file_hash(file_path)
                            
                            update_cache(
                                folder_name=folder_name,
                                folder_path=folder_path,
                                namespace=folder_name,
                                file_count=len(md_files),
                                chunk_count=total_chunks,
                                files=file_hashes
                            )
                            
                            console.print(f"[green]✓ Indexed {len(md_files)} files[/green]\n")
                    else:
                        console.print("[yellow]Cannot answer without indexed context.[/yellow]")
                        raise typer.Exit(1)
                else:
                    console.print("[yellow]No markdown files found in folder.[/yellow]")
                    raise typer.Exit(1)
            
            target_namespace = folder_name
            console.print(f"[dim]Using @{folder_name}[/dim]\n")
        
        # Get the actual question
        clean_question = remove_folder_references(question)
        
        if not clean_question:
            console.print("[red]Please provide a question.[/red]")
            raise typer.Exit(1)
        
        # Show question
        console.print(f"[bold cyan]Q:[/bold cyan] {clean_question}\n")
        
        # Call backend
        async with get_client() as client:
            try:
                if stream:
                    # Streaming response
                    console.print("[bold green]🤖[/bold green] ", end="")
                    full_response = ""
                    
                    async for event in client.ask_stream(
                        question=clean_question,
                        namespace=target_namespace,
                        provider=provider,
                        model=model,
                        temperature=temperature,
                        thread_id=thread_id
                    ):
                        if "token" in event:
                            console.print(event["token"], end="")
                            full_response += event["token"]
                    
                    console.print()  # New line
                    
                else:
                    # Non-streaming response
                    result = await client.ask(
                        question=clean_question,
                        namespace=target_namespace,
                        provider=provider,
                        model=model,
                        temperature=temperature,
                        thread_id=thread_id
                    )
                    
                    console.print(f"[bold green]🤖[/bold green] {result['answer']}")
                    
                    # Show sources
                    if result.get('sources'):
                        sources_str = ", ".join([
                            f"{s.get('source', 'unknown')}"
                            for s in result['sources'][:3]
                        ])
                        console.print(f"\n[dim]Sources: {sources_str}[/dim]")
                    
                    # Show usage
                    if result.get('usage'):
                        usage = result['usage']
                        console.print(f"[dim]Tokens: {usage.get('total_tokens', 0)}[/dim]")
                
            except APIError as e:
                console.print(f"[red]Error: {e.message}[/red]")
                raise typer.Exit(1)
    
    asyncio.run(_ask())


# Default command - runs interactive chat
@app.callback(invoke_without_command=True)
def chat_default(
    ctx: typer.Context,
    provider: str = typer.Option("openai", "--provider", "-p", help="LLM provider"),
    folder: str = typer.Option(None, "--folder", "-f", help="Pre-load a folder context")
):
    """
    Start interactive chat (default) or use subcommands for single-shot questions.
    
    Run without arguments to start interactive TUI:
        mdcli chat
    
    Or use subcommands:
        mdcli chat interactive
        mdcli chat ask "Your question"
    """
    if ctx.invoked_subcommand is None:
        # Run interactive chat
        chat_interactive(provider=provider, folder=folder)
