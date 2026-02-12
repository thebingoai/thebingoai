"""TUI modals for confirmation dialogs."""

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
