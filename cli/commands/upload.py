"""Upload command - Upload markdown files to the vector store."""

import asyncio
import typer
from pathlib import Path
from typing import Optional, List
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.prompt import Confirm

from cli.api.client import get_client, APIError
from cli.config import get_config
from cli.cache.index_cache import update_cache, get_file_hash
from cli.resolver.folder_resolver import get_folder_file_count

console = Console()
app = typer.Typer(help="Upload markdown files")


@app.command("file")
def upload_file(
    file: Path = typer.Argument(..., exists=True, help="Path to markdown file to upload"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Namespace for the file"),
    tags: List[str] = typer.Option([], "--tag", "-t", help="Tags for the file"),
    webhook_url: Optional[str] = typer.Option(None, "--webhook", "-w", help="Webhook URL for async completion"),
    force_async: bool = typer.Option(False, "--async", "-a", help="Force async processing"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """Upload a single markdown file to the vector store."""
    async def _upload():
        config = get_config()
        url = backend_url or config.backend_url

        console.print(f"Uploading {file.name}...")

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
                    console.print(f"[green]✓[/green] File queued for async processing")
                    console.print(f"  Job ID: {job_id}")
                    console.print(f"  Namespace: {namespace}")
                else:
                    console.print(f"[green]✓[/green] File uploaded and indexed")
                    console.print(f"  File: {result.get('filename')}")
                    console.print(f"  Chunks: {result.get('chunk_count')}")
                    console.print(f"  Namespace: {namespace}")

            except APIError as e:
                console.print(f"[red]Error: {e.message}[/red]")
                raise typer.Exit(1)

    asyncio.run(_upload())


@app.command("folder")
def upload_folder(
    folder: Path = typer.Argument(..., exists=True, help="Path to folder containing markdown files"),
    namespace: Optional[str] = typer.Option(None, "--namespace", "-n", help="Namespace (defaults to folder name)"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R", help="Recursively upload subdirectories"),
    pattern: str = typer.Option("*.md", "--pattern", "-p", help="File pattern to match"),
    tags: List[str] = typer.Option([], "--tag", "-t", help="Tags for all files"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """Upload all markdown files from a folder."""
    async def _upload_folder():
        config = get_config()
        url = backend_url or config.backend_url
        
        folder_path = Path(folder)
        folder_name = namespace or folder_path.name
        
        # Find all matching files
        if recursive:
            files = list(folder_path.glob(f"**/{pattern}"))
        else:
            files = list(folder_path.glob(pattern))
        
        if not files:
            console.print(f"[yellow]No {pattern} files found in {folder_path}[/yellow]")
            raise typer.Exit(0)
        
        console.print(f"\n[cyan]📁 {folder_path.name}[/cyan]")
        console.print(f"  Files found: {len(files)}")
        console.print(f"  Namespace: {folder_name}")
        console.print(f"  Recursive: {recursive}\n")
        
        if not Confirm.ask("Upload these files?", default=True):
            console.print("[dim]Cancelled.[/dim]")
            return
        
        async with get_client() as client:
            total_chunks = 0
            file_hashes = {}
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Uploading...", total=len(files))
                
                for i, file_path in enumerate(files):
                    rel_path = str(file_path.relative_to(folder_path))
                    progress.update(task, description=f"Uploading {rel_path}")
                    
                    try:
                        result = await client.upload_file(
                            file_path=file_path,
                            namespace=folder_name,
                            tags=tags + [folder_name]
                        )
                        
                        if result.get("chunks_created"):
                            total_chunks += result["chunks_created"]
                        
                        # Track file hash for cache
                        file_hashes[rel_path] = get_file_hash(file_path)
                        
                    except APIError as e:
                        console.print(f"[red]  Error uploading {rel_path}: {e.message}[/red]")
                    
                    progress.advance(task)
            
            # Update local cache
            update_cache(
                folder_name=folder_name,
                folder_path=folder_path,
                namespace=folder_name,
                file_count=len(files),
                chunk_count=total_chunks,
                files=file_hashes
            )
            
            console.print(f"\n[green]✓ Upload complete![/green]")
            console.print(f"  Files: {len(files)}")
            console.print(f"  Chunks: {total_chunks}")
            console.print(f"  Namespace: {folder_name}")
    
    asyncio.run(_upload_folder())


@app.command("batch")
def upload_batch(
    paths: List[Path] = typer.Argument(..., help="Files or folders to upload"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Namespace for all files"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", "-r/-R", help="Recursively process directories"),
    pattern: str = typer.Option("*.md", "--pattern", "-p", help="File pattern to match for directories"),
    tags: List[str] = typer.Option([], "--tag", "-t", help="Tags for all files"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """Upload multiple files or folders at once."""
    async def _upload_batch():
        config = get_config()
        url = backend_url or config.backend_url
        
        # Collect all files
        all_files = []
        for path in paths:
            path = Path(path)
            if path.is_file():
                all_files.append(path)
            elif path.is_dir():
                if recursive:
                    all_files.extend(path.glob(f"**/{pattern}"))
                else:
                    all_files.extend(path.glob(pattern))
        
        # Remove duplicates while preserving order
        seen = set()
        unique_files = []
        for f in all_files:
            if f.resolve() not in seen:
                seen.add(f.resolve())
                unique_files.append(f)
        all_files = unique_files
        
        if not all_files:
            console.print("[yellow]No files to upload.[/yellow]")
            raise typer.Exit(0)
        
        console.print(f"\n[cyan]📦 Batch Upload[/cyan]")
        console.print(f"  Files: {len(all_files)}")
        console.print(f"  Namespace: {namespace}\n")
        
        if not Confirm.ask("Upload these files?", default=True):
            console.print("[dim]Cancelled.[/dim]")
            return
        
        async with get_client() as client:
            success_count = 0
            error_count = 0
            total_chunks = 0
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console
            ) as progress:
                task = progress.add_task("Uploading...", total=len(all_files))
                
                for file_path in all_files:
                    progress.update(task, description=f"Uploading {file_path.name}")
                    
                    try:
                        result = await client.upload_file(
                            file_path=file_path,
                            namespace=namespace,
                            tags=tags
                        )
                        
                        if result.get("chunks_created"):
                            total_chunks += result["chunks_created"]
                        
                        success_count += 1
                        
                    except APIError as e:
                        console.print(f"[red]  Error: {file_path.name} - {e.message}[/red]")
                        error_count += 1
                    
                    progress.advance(task)
            
            console.print(f"\n[green]✓ Batch upload complete![/green]")
            console.print(f"  Success: {success_count}")
            if error_count:
                console.print(f"  Errors: {error_count}")
            console.print(f"  Total chunks: {total_chunks}")
    
    asyncio.run(_upload_batch())


# Backward compatibility - keep old command name
@app.command("single", hidden=True)
def upload_single(
    file: Path = typer.Argument(..., exists=True, help="Path to markdown file to upload"),
    namespace: str = typer.Option("default", "--namespace", "-n", help="Namespace for the file"),
    tags: List[str] = typer.Option([], "--tag", "-t", help="Tags for the file"),
    backend_url: Optional[str] = typer.Option(None, "--backend-url", "-b", help="Backend API URL")
):
    """Upload a single file (legacy command)."""
    upload_file(file, namespace, tags, None, False, backend_url)
