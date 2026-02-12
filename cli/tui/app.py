"""TUI Chat Application - Claude Code-style interactive chat."""

from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Input, Static, RichLog
from textual.binding import Binding
from textual import work
from pathlib import Path

from cli.config import get_config
from cli.cache.index_cache import (
    is_folder_indexed,
    get_folder_info,
    update_cache,
    get_file_hash,
    get_changed_files
)
from cli.resolver.folder_resolver import (
    extract_folder_references,
    remove_folder_references,
    resolve_folder
)
from cli.api.client import BackendClient, APIError
from cli.tui.modals import ConfirmModal


class ChatApp(App):
    """Claude Code-style TUI chat application."""

    CSS = """
    /* Main layout */
    #chat-container {
        height: 100%;
    }

    /* Message area - scrollable */
    #messages {
        height: 1fr;
        border: solid $primary;
        padding: 1;
        overflow-y: auto;
    }

    /* Status bar above input */
    #status-bar {
        height: 1;
        background: $surface;
        color: $text-muted;
        padding: 0 1;
    }

    /* Input container at bottom */
    #input-container {
        height: auto;
        max-height: 5;
        border: solid $accent;
        padding: 0 1;
    }

    #input-field {
        border: none;
        padding: 0;
    }

    /* Message styling */
    .user-message {
        color: $text;
        margin: 1 0;
    }

    .assistant-message {
        color: $success;
        margin: 1 0;
    }

    .system-message {
        color: $warning;
        text-style: italic;
        margin: 1 0;
    }

    /* Header customization */
    Header {
        background: $primary;
    }
    """

    BINDINGS = [
        Binding("ctrl+c", "cancel", "Cancel", show=True),
        Binding("ctrl+d", "quit", "Exit", show=True),
        Binding("up", "history_prev", "Previous", show=False),
        Binding("down", "history_next", "Next", show=False),
        Binding("escape", "clear_input", "Clear", show=False),
    ]

    def __init__(self, backend_url: str = None, provider: str = "openai", folder: str = None):
        super().__init__()
        config = get_config()
        self.backend_url = backend_url or config.backend_url
        self.provider = provider
        self.current_namespace = folder
        self.thread_id = None
        self.history = []
        self.input_history = []
        self.history_index = -1

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header(show_clock=False)
        with Vertical(id="chat-container"):
            yield RichLog(id="messages", highlight=True, markup=True)
            yield Static(id="status-bar")
            with Container(id="input-container"):
                yield Input(
                    placeholder="Type your message... (@folder for context, /help for commands)",
                    id="input-field"
                )
        yield Footer()

    def on_mount(self) -> None:
        """Called when app starts."""
        self._update_header()
        self._update_status()
        self._show_welcome()
        self.query_one("#input-field", Input).focus()
        
        # If folder was pre-loaded, check if indexed
        if self.current_namespace:
            self.run_worker(self._check_preloaded_folder())

    async def _check_preloaded_folder(self):
        """Check if pre-loaded folder is indexed."""
        if not is_folder_indexed(self.current_namespace):
            log = self.query_one("#messages", RichLog)
            log.write(f"[yellow]Note: @{self.current_namespace} is not indexed yet.[/yellow]")
            log.write("Use [dim]/index @{self.current_namespace}[/dim] to index it.\n")

    def _update_header(self) -> None:
        """Update header with current context."""
        title = "mdcli"
        if self.current_namespace:
            title += f" │ @{self.current_namespace}"
        title += f" │ {self.provider}"
        self.title = title

    def _update_status(self) -> None:
        """Update status bar."""
        status = self.query_one("#status-bar", Static)
        ctx = f"Context: @{self.current_namespace}" if self.current_namespace else "No context"
        status.update(f"{ctx} │ Provider: {self.provider}")

    def _show_welcome(self) -> None:
        """Display welcome message."""
        log = self.query_one("#messages", RichLog)
        log.write("[bold blue]Welcome to mdcli![/bold blue]")
        log.write("Type your question or use [cyan]@folder[/cyan] to reference files.")
        log.write("Type [dim]/help[/dim] for commands.\n")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Enter key in input field."""
        user_input = event.value.strip()
        if not user_input:
            return

        # Clear input and add to history
        input_field = self.query_one("#input-field", Input)
        input_field.value = ""
        self.input_history.append(user_input)
        self.history_index = len(self.input_history)

        # Process the input
        if user_input.startswith("/"):
            await self._handle_command(user_input)
        else:
            await self._process_message(user_input)

    async def _handle_command(self, cmd: str) -> None:
        """Handle slash commands."""
        log = self.query_one("#messages", RichLog)
        cmd_lower = cmd.lower().strip()

        if cmd_lower in ["/quit", "/exit"]:
            self.exit()

        elif cmd_lower == "/help":
            self._show_help()

        elif cmd_lower == "/clear":
            log.clear()
            self._show_welcome()

        elif cmd_lower.startswith("/index "):
            folder = cmd[7:].strip().lstrip("@")
            await self._index_folder(folder, force=True)

        elif cmd_lower == "/status":
            self._show_status()

        elif cmd_lower.startswith("/provider "):
            provider = cmd[10:].strip()
            self.provider = provider
            self._update_header()
            self._update_status()
            log.write(f"[green]Provider switched to: {provider}[/green]")

        else:
            log.write(f"[yellow]Unknown command: {cmd}[/yellow]")

    def _show_help(self) -> None:
        """Show available commands."""
        log = self.query_one("#messages", RichLog)
        help_text = """
[bold]Commands:[/bold]
  /help              Show this help
  /quit              Exit chat
  /clear             Clear messages
  /index @folder     Force re-index a folder
  /status            Show current context
  /provider <name>   Switch provider (openai/anthropic/ollama)

[bold]Usage:[/bold]
  @folder-name       Reference a folder (prompts to index if needed)
  Just type          Ask questions using current context

[bold]Keys:[/bold]
  ↑/↓                Navigate input history
  Ctrl+C             Cancel current operation
  Ctrl+D             Exit
"""
        log.write(help_text)

    def _show_status(self) -> None:
        """Show current status."""
        log = self.query_one("#messages", RichLog)
        log.write(f"\n[bold]Status:[/bold]")
        log.write(f"  Context: {'@' + self.current_namespace if self.current_namespace else 'None'}")
        log.write(f"  Provider: {self.provider}")
        log.write(f"  Backend: {self.backend_url}")
        log.write(f"  Messages: {len(self.history)}\n")

    async def _process_message(self, user_input: str) -> None:
        """Process user message with @folder reference."""
        log = self.query_one("#messages", RichLog)

        # Show user message
        log.write(f"\n[bold cyan]You:[/bold cyan] {user_input}")

        # Extract @folder reference
        folder_refs = extract_folder_references(user_input)

        if len(folder_refs) > 1:
            log.write("[yellow]Please reference only one folder at a time.[/yellow]")
            return

        if folder_refs:
            folder_ref = folder_refs[0]
            resolved = resolve_folder(folder_ref)

            if not resolved:
                log.write(f"[red]Folder '{folder_ref}' not found.[/red]")
                return

            folder_path, folder_name = resolved

            # Check if indexed
            indexed = await self._ensure_indexed(folder_name, folder_path)
            if not indexed:
                return

            self.current_namespace = folder_name
            self._update_header()
            self._update_status()

        # Get the question
        question = remove_folder_references(user_input)

        if not question:
            log.write(f"[dim]Context set to @{self.current_namespace}. Ask a question![/dim]")
            return

        if not self.current_namespace:
            log.write("[yellow]No folder context. Use @folder to reference your files.[/yellow]")
            return

        # Send to backend
        await self._ask_with_rag(question)

    async def _ensure_indexed(self, folder_name: str, folder_path: Path) -> bool:
        """Check if folder is indexed, prompt to index if not."""
        log = self.query_one("#messages", RichLog)

        if is_folder_indexed(folder_name):
            info = get_folder_info(folder_name)
            log.write(f"[dim]Using @{folder_name} ({info['file_count']} files)[/dim]")
            return True

        # Count files
        md_files = list(Path(folder_path).glob("**/*.md"))

        log.write(f"\n📁 [cyan]@{folder_name}[/cyan] found ({len(md_files)} files)")
        log.write("[dim]This folder is not indexed yet.[/dim]")

        # Show confirmation modal
        confirmed = await self.push_screen_wait(ConfirmModal(
            title="Index Folder?",
            message=f"Index @{folder_name} ({len(md_files)} markdown files)?"
        ))

        if not confirmed:
            log.write("[dim]Indexing skipped.[/dim]")
            return False

        return await self._index_folder(folder_name, folder_path)

    async def _index_folder(self, folder_name: str, folder_path: Path = None, force: bool = False) -> bool:
        """Index folder's markdown files."""
        log = self.query_one("#messages", RichLog)

        if folder_path is None:
            resolved = resolve_folder(folder_name)
            if not resolved:
                log.write(f"[red]Folder '{folder_name}' not found.[/red]")
                return False
            folder_path, folder_name = resolved

        folder_path = Path(folder_path)
        md_files = list(folder_path.glob("**/*.md"))
        total = len(md_files)

        if total == 0:
            log.write(f"[yellow]No markdown files found in @{folder_name}[/yellow]")
            return False

        # Show progress in message area
        log.write(f"⏳ Indexing @{folder_name}...")

        # Upload each file to backend
        total_chunks = 0
        file_hashes = {}

        try:
            async with BackendClient(self.backend_url) as client:
                for i, file_path in enumerate(md_files):
                    rel_path = str(file_path.relative_to(folder_path))
                    log.write(f"[dim]  Uploading {rel_path} ({i+1}/{total})...[/dim]")

                    result = await client.upload_file(
                        file_path=file_path,
                        namespace=folder_name,
                        tags=[folder_name]
                    )

                    if result.get("chunks_created"):
                        total_chunks += result["chunks_created"]

                    # Track file hash for cache
                    file_hashes[rel_path] = get_file_hash(file_path)

            # Update local cache
            update_cache(
                folder_name=folder_name,
                folder_path=folder_path,
                namespace=folder_name,
                file_count=total,
                chunk_count=total_chunks,
                files=file_hashes
            )

            log.write(f"[green]✓ Indexed {total} files ({total_chunks} chunks)[/green]")
            return True

        except APIError as e:
            log.write(f"[red]Error indexing: {e.message}[/red]")
            return False
        except Exception as e:
            log.write(f"[red]Error: {str(e)}[/red]")
            return False

    async def _ask_with_rag(self, question: str) -> None:
        """Send question to backend using LangGraph and stream response."""
        log = self.query_one("#messages", RichLog)

        # Add to history
        self.history.append({"role": "user", "content": question})

        # Show thinking indicator
        log.write("\n[bold green]🤖[/bold green] [dim]Thinking...[/dim]")

        try:
            async with BackendClient(self.backend_url) as client:
                full_response = ""
                sources = []

                # Stream response from backend
                async for event in client.ask_stream(
                    question=question,
                    namespace=self.current_namespace,
                    provider=self.provider,
                    thread_id=self.thread_id
                ):
                    if "sources" in event:
                        sources = event["sources"]
                    elif "token" in event:
                        full_response += event["token"]
                    elif "thread_id" in event:
                        self.thread_id = event["thread_id"]

                # Display final response
                log.write(f"[bold green]🤖[/bold green] {full_response}")

                # Show sources
                if sources:
                    sources_str = ", ".join([
                        f"{s.get('source', 'unknown')}"
                        for s in sources[:3]
                    ])
                    log.write(f"[dim]Sources: {sources_str}[/dim]")

                self.history.append({"role": "assistant", "content": full_response})

        except APIError as e:
            log.write(f"[red]Error: {e.message}[/red]")
            self.history.append({"role": "assistant", "content": f"Error: {e.message}"})
        except Exception as e:
            log.write(f"[red]Error: {str(e)}[/red]")
            self.history.append({"role": "assistant", "content": f"Error: {str(e)}"})

    def action_history_prev(self) -> None:
        """Navigate to previous input in history."""
        if self.input_history and self.history_index > 0:
            self.history_index -= 1
            input_field = self.query_one("#input-field", Input)
            input_field.value = self.input_history[self.history_index]

    def action_history_next(self) -> None:
        """Navigate to next input in history."""
        input_field = self.query_one("#input-field", Input)
        if self.history_index < len(self.input_history) - 1:
            self.history_index += 1
            input_field.value = self.input_history[self.history_index]
        else:
            self.history_index = len(self.input_history)
            input_field.value = ""

    def action_clear_input(self) -> None:
        """Clear the input field."""
        input_field = self.query_one("#input-field", Input)
        input_field.value = ""

    def action_cancel(self) -> None:
        """Cancel current operation."""
        log = self.query_one("#messages", RichLog)
        log.write("[dim]Cancelled[/dim]")

    def action_quit(self) -> None:
        """Exit the application."""
        self.exit()
