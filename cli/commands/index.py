"""Index management commands - List, delete, and manage indexed folders."""

import asyncio
import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Confirm

from cli.cache.index_cache import (
    list_indexed_folders,
    delete_folder_cache,
    get_folder_info,
    clear_cache
)
from cli.resolver.folder_resolver import resolve_folder, get_folder_file_count
from cli.api.client import get_client, APIError
from cli.config import get_config

console = Console()
app = typer.Typer(help="Manage indexed folders")


@app.command("list")
def list_indexes():
    """List all indexed folders."""
    folders = list_indexed_folders()
    
    if not folders:
        console.print("[yellow]No folders indexed yet.[/yellow]")
        console.print("Use [cyan]mdcli upload[/cyan] or [cyan]mdcli chat[/cyan] to index folders.")
        return
    
    table = Table(title="Indexed Folders")
    table.add_column("Name", style="cyan")
    table.add_column("Path", style="dim")
    table.add_column("Namespace", style="green")
    table.add_column("Files", justify="right")
    table.add_column("Chunks", justify="right")
    table.add_column("Indexed At", style="dim")
    
    for folder in folders:
        table.add_row(
            folder["name"],
            folder.get("path", "N/A"),
            folder.get("namespace", "N/A"),
            str(folder.get("file_count", 0)),
            str(folder.get("chunk_count", 0)),
            folder.get("indexed_at", "N/A")[:19]  # Truncate to date
        )
    
    console.print(table)
    console.print(f"\n[dim]Total: {len(folders)} folder(s)[/dim]")


@app.command("stats")
def index_stats(
    folder: str = typer.Argument(..., help="Folder name to show stats for")
):
    """Show detailed statistics for an indexed folder."""
    info = get_folder_info(folder)
    
    if not info:
        console.print(f"[red]Folder '{folder}' is not indexed.[/red]")
        console.print("Use [cyan]mdcli index list[/cyan] to see indexed folders.")
        raise typer.Exit(1)
    
    console.print(f"\n[bold cyan]📁 {folder}[/bold cyan]\n")
    console.print(f"  Path: {info.get('path', 'N/A')}")
    console.print(f"  Namespace: {info.get('namespace', 'N/A')}")
    console.print(f"  Files: {info.get('file_count', 0)}")
    console.print(f"  Chunks: {info.get('chunk_count', 0)}")
    console.print(f"  Indexed: {info.get('indexed_at', 'N/A')}")
    
    files = info.get("files", {})
    if files:
        console.print(f"\n[dim]Tracked files: {len(files)}[/dim]")


@app.command("delete")
def delete_index(
    folder: str = typer.Argument(..., help="Folder name to delete from index"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Delete a folder from the local index cache."""
    info = get_folder_info(folder)
    
    if not info:
        console.print(f"[red]Folder '{folder}' is not indexed.[/red]")
        raise typer.Exit(1)
    
    if not force:
        console.print(f"[yellow]This will remove '{folder}' from the local cache.[/yellow]")
        console.print("[dim]Note: This does not delete data from Pinecone.[/dim]")
        if not Confirm.ask("Continue?", default=False):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)
    
    if delete_folder_cache(folder):
        console.print(f"[green]✓ Deleted '{folder}' from local cache.[/green]")
    else:
        console.print(f"[red]Failed to delete '{folder}'.[/red]")


@app.command("clear")
def clear_index_cache(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation")
):
    """Clear all local index cache (does not affect Pinecone)."""
    folders = list_indexed_folders()
    
    if not folders:
        console.print("[yellow]No folders to clear.[/yellow]")
        return
    
    if not force:
        console.print(f"[yellow]This will clear all {len(folders)} folder(s) from local cache.[/yellow]")
        console.print("[dim]Note: This does not delete data from Pinecone.[/dim]")
        if not Confirm.ask("Continue?", default=False):
            console.print("[dim]Cancelled.[/dim]")
            raise typer.Exit(0)
    
    clear_cache()
    console.print("[green]✓ Cleared all index cache.[/green]")


@app.command("refresh")
def refresh_index(
    folder: str = typer.Argument(..., help="Folder name to refresh"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """Re-index a folder, uploading only changed files."""
    async def _refresh():
        from cli.cache.index_cache import (
            get_changed_files,
            get_removed_files,
            update_cache,
            get_file_hash
        )
        from cli.resolver.folder_resolver import resolve_folder
        
        config = get_config()
        url = backend_url or config.backend_url
        
        # Get folder info
        info = get_folder_info(folder)
        if not info:
            console.print(f"[red]Folder '{folder}' is not indexed.[/red]")
            raise typer.Exit(1)
        
        folder_path = Path(info["path"])
        if not folder_path.exists():
            # Try to resolve again
            resolved = resolve_folder(folder)
            if resolved:
                folder_path, _ = resolved
            else:
                console.print(f"[red]Folder path not found: {info['path']}[/red]")
                raise typer.Exit(1)
        
        # Check for changes
        changed_files = get_changed_files(folder, folder_path)
        removed_files = get_removed_files(folder, folder_path)
        
        if not changed_files and not removed_files:
            console.print(f"[green]✓ '{folder}' is up to date. No changes detected.[/green]")
            return
        
        console.print(f"\n[cyan]📁 {folder}[/cyan]")
        console.print(f"  Changed files: {len(changed_files)}")
        console.print(f"  Removed files: {len(removed_files)}")
        
        if not Confirm.ask("\nRe-index changed files?", default=True):
            console.print("[dim]Cancelled.[/dim]")
            return
        
        # Re-index
        console.print("\n[dim]Refreshing index...[/dim]")
        
        try:
            async with get_client() as client:
                total_chunks = 0
                file_hashes = {}
                
                # Upload changed files
                for file_path in changed_files:
                    rel_path = str(file_path.relative_to(folder_path))
                    console.print(f"  Uploading {rel_path}...")
                    
                    result = await client.upload_file(
                        file_path=file_path,
                        namespace=info["namespace"],
                        tags=[folder]
                    )
                    
                    if result.get("chunks_created"):
                        total_chunks += result["chunks_created"]
                    
                    file_hashes[rel_path] = get_file_hash(file_path)
                
                # Update cache
                all_files = info.get("files", {})
                all_files.update(file_hashes)
                
                # Remove deleted files from cache
                for removed in removed_files:
                    if removed in all_files:
                        del all_files[removed]
                
                # Get current file count
                current_files = list(folder_path.glob("**/*.md"))
                
                update_cache(
                    folder_name=folder,
                    folder_path=folder_path,
                    namespace=info["namespace"],
                    file_count=len(current_files),
                    chunk_count=info.get("chunk_count", 0) + total_chunks,
                    files=all_files
                )
                
                console.print(f"\n[green]✓ Refresh complete![/green]")
                console.print(f"  Uploaded: {len(changed_files)} file(s)")
                if removed_files:
                    console.print(f"  Removed: {len(removed_files)} file(s)")
                
        except APIError as e:
            console.print(f"[red]Error: {e.message}[/red]")
            raise typer.Exit(1)
    
    asyncio.run(_refresh())
