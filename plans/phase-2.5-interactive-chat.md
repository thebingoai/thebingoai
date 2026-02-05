# Phase 2.5: Interactive Chat Mode with @folder References

## Overview
Add Claude Code-style interactive chat experience with @folder syntax for referencing and indexing folders. Uses a TUI (Text User Interface) with the input field fixed at the bottom, messages scrolling above.

## Duration: Integrated into Week 2-3

---

## UI Layout (Claude Code-style)

```
┌─────────────────────────────────────────────────────────────────┐
│ mdcli v0.1.0                              @my-notes │ anthropic │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  You: @my-notes What did I learn about embeddings?              │
│                                                                 │
│  📁 Indexing my-notes... ✓ Done (23 files)                      │
│                                                                 │
│  🤖 Based on your notes, embeddings are dense vector            │
│     representations that capture semantic meaning. Your notes   │
│     mention that OpenAI's text-embedding-3-large produces       │
│     3072-dimensional vectors...                                 │
│                                                                 │
│  You: What about transformers?                                  │
│                                                                 │
│  🤖 Your notes discuss transformers as the architecture         │
│     behind modern LLMs. Key points include:                     │
│     • Self-attention mechanism                                  │
│     • Parallel processing of sequences                          │
│     • Positional encodings...                                   │
│                                                                 │
│                                              ▼ scroll for more  │
├─────────────────────────────────────────────────────────────────┤
│ > Type your message... (@folder for context, /help for commands)│
└─────────────────────────────────────────────────────────────────┘
  Ctrl+C to cancel | Ctrl+D to exit | ↑↓ for history
```

### Key UI Elements
- **Header bar:** App name, current context (@folder), active provider
- **Message area:** Scrollable conversation history
- **Input field:** Fixed at bottom, always visible
- **Status bar:** Keyboard shortcuts, connection status
- **Modal dialogs:** Confirmation prompts overlay the chat area

### Confirmation Flow

When referencing an unindexed folder:

```
┌─────────────────────────────────────────────────────────────────┐
│ mdcli v0.1.0                                          │ openai  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  You: @my-notes What did I learn?                               │
│                                                                 │
│  📁 @my-notes found (23 files)                                  │
│  This folder is not indexed yet.                                │
│                                                                 │
│        ┌──────────────────────────────────────────┐             │
│        │           Index Folder?                  │             │
│        │                                          │             │
│        │  Index @my-notes (23 markdown files)?    │             │
│        │                                          │             │
│        │       [ Yes [Y] ]    [ No [N] ]          │             │
│        └──────────────────────────────────────────┘             │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ > (waiting for confirmation...)                                 │
└─────────────────────────────────────────────────────────────────┘
  Press Y to confirm | N to skip
```

---

## Task 2.5.1: Index Cache System

### Create `cli/cache/index_cache.py`

**Cache file location:** `~/.mdcli/index_cache.json`

```json
{
  "indexes": {
    "my-notes": {
      "path": "/Users/you/Documents/my-notes",
      "namespace": "my-notes",
      "indexed_at": "2024-01-15T10:30:00Z",
      "file_count": 23,
      "chunk_count": 47,
      "files": {
        "note1.md": {
          "hash": "abc123...",
          "indexed_at": "2024-01-15T10:30:00Z"
        }
      }
    }
  }
}
```

**Functions:**

```python
from pathlib import Path
from datetime import datetime
import hashlib
import json

CACHE_FILE = Path.home() / ".mdcli" / "index_cache.json"

def get_file_hash(file_path: Path) -> str:
    """Get MD5 hash of file content."""
    return hashlib.md5(file_path.read_bytes()).hexdigest()

def is_folder_indexed(folder_name: str) -> bool:
    """Check if folder has been indexed."""
    pass

def get_folder_info(folder_name: str) -> dict | None:
    """Get cached info about an indexed folder."""
    pass

def get_changed_files(folder_name: str, folder_path: Path) -> list[Path]:
    """Compare current files with cache, return changed/new files."""
    pass

def update_cache(
    folder_name: str,
    folder_path: Path,
    namespace: str,
    file_count: int,
    chunk_count: int,
    files: dict[str, str]  # filename -> hash
) -> None:
    """Update cache after successful indexing."""
    pass

def clear_cache(folder_name: str = None) -> None:
    """Clear cache for specific folder or all."""
    pass
```

---

## Task 2.5.2: Folder Resolution

### Create `cli/resolver/folder_resolver.py`

**Resolution rules:**
1. Check if name matches a cached folder name
2. Check if it's a path relative to current directory
3. Check if it's an absolute path
4. Check common locations (~/Documents, ~/Desktop, etc.)

```python
from pathlib import Path

def resolve_folder(reference: str) -> tuple[Path, str] | None:
    """
    Resolve @folder reference to actual path.

    Args:
        reference: Folder reference (e.g., "my-notes", "./docs", "~/Documents/notes")

    Returns:
        (folder_path, folder_name) or None if not found

    Resolution order:
        1. Cached folder name
        2. Relative path from cwd
        3. Absolute path
        4. Common locations search
    """
    pass

def extract_folder_references(text: str) -> list[str]:
    """
    Extract @folder references from user input.

    Examples:
        "What's in @my-notes?" -> ["my-notes"]
        "@docs explain this" -> ["docs"]
        "no reference here" -> []
    """
    import re
    pattern = r'@([a-zA-Z0-9_-]+|"[^"]+"|\S+)'
    matches = re.findall(pattern, text)
    return [m.strip('"') for m in matches]

def remove_folder_references(text: str) -> str:
    """Remove @folder references from text, leaving the question."""
    import re
    return re.sub(r'@([a-zA-Z0-9_-]+|"[^"]+"|\S+)\s*', '', text).strip()
```

---

## Task 2.5.3: TUI Dependencies

### Update `cli/requirements.txt`

```
typer==0.9.0
httpx==0.26.0
rich==13.7.0
pyyaml==6.0.1
textual==0.47.1          # TUI framework (Claude Code-style layout)
prompt_toolkit==3.0.43   # Advanced input handling
```

---

## Task 2.5.4: TUI App Structure

### Create `cli/tui/__init__.py`

### Create `cli/tui/app.py`

```python
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical, Horizontal
from textual.widgets import Header, Footer, Input, Static, RichLog
from textual.binding import Binding
from textual import events

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

    def __init__(self, backend_url: str, provider: str = "openai"):
        super().__init__()
        self.backend_url = backend_url
        self.provider = provider
        self.current_namespace = None
        self.thread_id = None  # LangGraph conversation thread
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
        from cli.resolver.folder_resolver import (
            extract_folder_references,
            remove_folder_references,
            resolve_folder
        )

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
            log.write("[dim]Context set to @{self.current_namespace}. Ask a question![/dim]")
            return

        if not self.current_namespace:
            log.write("[yellow]No folder context. Use @folder to reference your files.[/yellow]")
            return

        # Send to backend
        await self._ask_with_rag(question)

    async def _ensure_indexed(self, folder_name: str, folder_path) -> bool:
        """Check if folder is indexed, prompt to index if not."""
        from cli.cache.index_cache import is_folder_indexed, get_folder_info
        from pathlib import Path

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
        confirmed = await self._show_confirm_modal(
            title="Index Folder?",
            message=f"Index @{folder_name} ({len(md_files)} markdown files)?",
        )

        if not confirmed:
            log.write("[dim]Indexing skipped.[/dim]")
            return False

        return await self._index_folder(folder_name, folder_path)

    async def _show_confirm_modal(self, title: str, message: str) -> bool:
        """Show a confirmation modal and wait for user response."""
        from cli.tui.modals import ConfirmModal

        modal = ConfirmModal(title=title, message=message)
        result = await self.push_screen_wait(modal)
        return result

    async def _index_folder(self, folder_name: str, folder_path=None, force: bool = False) -> bool:
        """Index folder's markdown files."""
        from cli.resolver.folder_resolver import resolve_folder
        from cli.api.client import BackendClient
        from cli.cache.index_cache import update_cache, get_file_hash
        from pathlib import Path

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

        except Exception as e:
            log.write(f"[red]Error indexing: {e}[/red]")
            return False

    async def _ask_with_rag(self, question: str) -> None:
        """Send question to backend using LangGraph and stream response."""
        from cli.api.client import BackendClient

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
                        f"{s['source']}#{s['chunk_index']}"
                        for s in sources[:3]
                    ])
                    log.write(f"[dim]Sources: {sources_str}[/dim]")

                self.history.append({"role": "assistant", "content": full_response})

        except Exception as e:
            log.write(f"[red]Error: {e}[/red]")
            self.history.append({"role": "assistant", "content": f"Error: {e}"})

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
```

---

## Task 2.5.5: Confirmation Modal

### Create `cli/tui/modals.py`

```python
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static, Label

class ConfirmModal(ModalScreen[bool]):
    """Modal dialog for confirmation prompts."""

    CSS = """
    ConfirmModal {
        align: center middle;
    }

    #modal-container {
        width: 60;
        height: auto;
        border: thick $primary;
        background: $surface;
        padding: 1 2;
    }

    #modal-title {
        text-style: bold;
        width: 100%;
        content-align: center middle;
        padding-bottom: 1;
    }

    #modal-message {
        width: 100%;
        padding-bottom: 1;
    }

    #button-row {
        width: 100%;
        height: auto;
        align: center middle;
        padding-top: 1;
    }

    #button-row Button {
        margin: 0 1;
    }

    #btn-yes {
        background: $success;
    }

    #btn-no {
        background: $error;
    }
    """

    BINDINGS = [
        ("y", "confirm", "Yes"),
        ("n", "cancel", "No"),
        ("enter", "confirm", "Confirm"),
        ("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str, message: str):
        super().__init__()
        self.modal_title = title
        self.modal_message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            yield Label(self.modal_title, id="modal-title")
            yield Static(self.modal_message, id="modal-message")
            with Horizontal(id="button-row"):
                yield Button("Yes [Y]", id="btn-yes", variant="success")
                yield Button("No [N]", id="btn-no", variant="error")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-yes":
            self.dismiss(True)
        else:
            self.dismiss(False)

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)
```

**Modal appearance:**

```
┌─────────────────────────────────────────────────────────────────┐
│                         (chat area)                             │
│                                                                 │
│        ┌──────────────────────────────────────────┐             │
│        │         Index Folder?                    │             │
│        │                                          │             │
│        │  Index @my-notes (23 markdown files)?    │             │
│        │                                          │             │
│        │        [ Yes [Y] ]    [ No [N] ]         │             │
│        └──────────────────────────────────────────┘             │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│ > Type your message...                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

## Task 2.5.6: Chat Command Entry Point

### Create `cli/cmd/chat.py`

```python
import typer
from cli.config import get_config

app = typer.Typer()

@app.command()
def chat(
    provider: str = typer.Option("openai", "--provider", "-p", help="LLM provider"),
    model: str = typer.Option(None, "--model", "-m", help="Model name"),
    folder: str = typer.Option(None, "--folder", "-f", help="Pre-load a folder context")
):
    """
    Start interactive chat session (Claude Code-style TUI).

    Examples:
        mdcli chat
        mdcli chat --folder my-notes
        mdcli chat --provider anthropic
    """
    from cli.tui.app import ChatApp

    config = get_config()

    app = ChatApp(
        backend_url=config.backend_url,
        provider=provider
    )

    # Pre-load folder if specified
    if folder:
        app.current_namespace = folder

    # Run the TUI
    app.run()
```

---

## Task 2.5.7: Single-Shot Ask with @folder

### Update `cli/cmd/ask.py`

```python
import typer
from rich.console import Console
from cli.resolver.folder_resolver import extract_folder_references, remove_folder_references, resolve_folder
from cli.cache.index_cache import is_folder_indexed

console = Console()

@app.command()
def ask(
    query: str = typer.Argument(..., help="Your question, optionally with @folder"),
    provider: str = typer.Option("openai", "--provider", "-p"),
    top_k: int = typer.Option(5, "--top-k", "-k"),
    show_sources: bool = typer.Option(False, "--sources", "-s")
):
    """
    Ask a single question with optional @folder context.

    Examples:
        mdcli ask "@my-notes What are embeddings?"
        mdcli ask "Explain transformers" --provider anthropic
    """
    # Extract folder reference
    folder_refs = extract_folder_references(query)

    namespace = None
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
            from rich.prompt import Confirm
            console.print(f"📁 Folder '{folder_name}' is not indexed.")

            if Confirm.ask("Index it now?", default=True):
                # Index the folder
                index_folder(folder_name, folder_path)
            else:
                console.print("[yellow]Cannot answer without indexed context.[/yellow]")
                raise typer.Exit(1)

        namespace = folder_name

    # Get the actual question
    question = remove_folder_references(query)

    if not question:
        console.print("[red]Please provide a question.[/red]")
        raise typer.Exit(1)

    if not namespace:
        console.print("[yellow]No @folder specified. Searching all indexed content.[/yellow]")
        namespace = "default"

    # Call backend
    # response = call_ask_endpoint(question, namespace, provider, top_k)
    # display_response(response, show_sources)
```

---

## Task 2.5.8: Update Main CLI

### Update `cli/main.py`

```python
import typer
from cli.cmd import config, upload, query, chat, ask, jobs, status

app = typer.Typer(
    name="mdcli",
    help="Chat with your markdown files using LLMs",
    no_args_is_help=True
)

# Subcommands
app.add_typer(config.app, name="config")
app.add_typer(jobs.app, name="jobs")

# Direct commands
app.command()(chat.chat)           # mdcli chat
app.command()(ask.ask)             # mdcli ask "question"
app.command()(upload.upload)       # mdcli upload (manual upload)
app.command()(query.query)         # mdcli query (raw vector search)
app.command()(status.status)       # mdcli status

if __name__ == "__main__":
    app()
```

---

## Updated CLI Commands Summary

```bash
# Interactive chat (primary mode)
mdcli chat
mdcli chat --provider anthropic
mdcli chat --folder my-notes        # Pre-load context

# Single-shot ask (with @folder support)
mdcli ask "@my-notes What are embeddings?"
mdcli ask "Explain this" --provider ollama

# Direct commands (still available)
mdcli upload ./folder/              # Manual upload
mdcli query "search term"           # Raw vector search
mdcli status                        # Check backend

# Config
mdcli config set-backend http://localhost:8000
mdcli config set-webhook https://...

# Jobs (for async uploads)
mdcli jobs list
mdcli jobs status <id>
```

---

## Interactive Session Commands

Inside `mdcli chat`:

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/quit` or `/exit` | Exit chat |
| `/clear` | Clear screen |
| `/index @folder` | Force re-index a folder |
| `/status` | Show current context & namespace |
| `/history` | Show conversation history |
| `/provider <name>` | Switch LLM provider |

---

## Verification Checklist

- [ ] Cache file created at `~/.mdcli/index_cache.json`
- [ ] @folder extraction works: `@my-notes`, `@"folder with spaces"`
- [ ] Folder resolution finds cached folders
- [ ] Folder resolution finds relative paths
- [ ] Prompt to index unindexed folders
- [ ] Index cache tracks file hashes
- [ ] Re-indexing only uploads changed files
- [ ] Interactive chat starts and accepts input
- [ ] /commands work correctly
- [ ] Single-shot `mdcli ask @folder question` works
- [ ] Chat history maintained within session

---

## Example Session

```
$ mdcli chat

┌─ 🤖 mdcli ─────────────────────────────────────────────┐
│ Welcome to mdcli!                                       │
│                                                         │
│ Type your question or use @folder to reference files.   │
│ Type /help for commands, /quit to exit.                 │
└─────────────────────────────────────────────────────────┘

You: @llm-notes What did I learn about embeddings?

📁 Folder 'llm-notes' found at ~/Documents/llm-notes
   15 markdown files found.
   This folder is not indexed yet.
   Index it now? [Y/n] y

⠋ Indexing llm-notes...
✓ Indexed 15 files (32 chunks)!

🤖 Based on your notes, you learned several key things about embeddings:

   1. Embeddings are dense vector representations that capture semantic meaning
   2. OpenAI's text-embedding-3-large produces 3072-dimensional vectors
   3. Similar concepts cluster together in the embedding space
   ...

You: What about the chunking strategy?

🤖 Your notes discuss a chunking strategy of 512 tokens with 20% overlap...

You: /provider anthropic
Provider switched to: anthropic (claude-sonnet-4-20250514)

You: Summarize everything about RAG

🤖 Based on your notes, here's a summary of RAG (Retrieval-Augmented Generation)...

You: /quit
Goodbye!
```
