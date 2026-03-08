"""Terminal display using rich."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass
class ActionRecord:
    """A single tool action performed by Claude."""

    name: str
    preview: str = ""


class Display:
    """Renders status, user input, and assistant responses in the terminal."""

    def __init__(self, max_width: int = 100, abort_presses: int = 3) -> None:
        self.console = Console(width=max_width)
        self._status_ctx = None
        self._actions: list[ActionRecord] = []
        self._abort_presses = abort_presses
        self._current_mode: str | None = None

    # ── Status helpers ──────────────────────────────────────────────

    def status(self, message: str) -> None:
        """Show a transient status line."""
        self.console.print(Text(f"  {message}", style="dim"))

    def ready(self) -> None:
        mode = self._current_mode or "Normal"
        self.status(f"Ready — hold hotkey to speak  [{mode} mode]")

    def mode_badge(self, sdk_mode: str) -> None:
        """Show the current operating mode."""
        labels = {
            "default": "Normal",
            "plan": "Plan",
            "acceptEdits": "Auto-edit",
        }
        label = labels.get(sdk_mode, sdk_mode)
        self._current_mode = label
        style = "bold magenta" if sdk_mode == "plan" else "bold cyan"
        self.console.print(Text(f"  Mode → {label}", style=style))

    def recording(self) -> None:
        self.console.print(Text("  🎙  Recording...", style="bold red"))

    def transcribing(self) -> None:
        self.console.print(Text("  Transcribing...", style="bold yellow"))

    # ── Streaming progress (replaces per-tool panels) ───────────────

    def start_streaming(self) -> None:
        """Begin the working spinner. Call record_action() as tools run."""
        self._actions = []
        hint = f"tap hotkey {self._abort_presses}x to abort"
        self._status_ctx = self.console.status(
            f"⚡ Working...  [dim]({hint})[/dim]",
            spinner="dots",
        )
        self._status_ctx.start()

    def record_action(self, name: str, input_preview: str = "") -> None:
        """Record a tool action and update the live spinner."""
        self._actions.append(ActionRecord(name, input_preview))
        self._update_spinner()

    def show_abort_progress(self, current: int) -> None:
        """Update the spinner to show how many abort taps have been registered."""
        if self._status_ctx is not None:
            n = len(self._actions)
            plural = "s" if n != 1 else ""
            action_info = f"{n} action{plural}" if n else ""
            self._status_ctx.update(
                f"⚡ Working... {action_info}"
                f"  [bold red]aborting: {current}/{self._abort_presses}[/bold red]"
            )

    def _update_spinner(self) -> None:
        """Refresh the spinner with current action count."""
        if self._status_ctx is not None:
            n = len(self._actions)
            plural = "s" if n != 1 else ""
            hint = f"tap hotkey {self._abort_presses}x to abort"
            self._status_ctx.update(
                f"⚡ Working... {n} action{plural} — latest: [bold yellow]{self._actions[-1].name}[/bold yellow]"
                f"  [dim]({hint})[/dim]"
            )

    def stop_streaming(self, *, aborted: bool = False) -> None:
        """Stop the spinner and print a consolidated action summary panel."""
        # Stop spinner (idempotent)
        if self._status_ctx is not None:
            self._status_ctx.stop()
            self._status_ctx = None

        # Print consolidated summary
        if self._actions:
            table = Table(
                show_header=False,
                show_edge=False,
                pad_edge=False,
                box=None,
            )
            table.add_column("#", style="dim", width=4, justify="right")
            table.add_column("Tool", style="bold yellow", min_width=10)
            table.add_column("Detail", style="dim", ratio=1)

            for i, action in enumerate(self._actions, 1):
                detail = action.preview.replace("\n", " ")[:80]
                table.add_row(str(i), action.name, detail)

            title = f"Actions ({len(self._actions)})"
            if aborted:
                title += " — aborted"
            self.console.print()
            self.console.print(
                Panel(table, title=title, border_style="yellow")
            )
            self._actions = []

    # ── Content panels ──────────────────────────────────────────────

    def user_text(self, text: str) -> None:
        """Display the transcribed user input."""
        self.console.print()
        self.console.print(Panel(text, title="You", border_style="green"))

    def assistant_text(self, text: str) -> None:
        """Render assistant markdown response."""
        self.console.print()
        self.console.print(Panel(Markdown(text), title="Claude", border_style="blue"))

    def tool_use(self, name: str, input_preview: str = "") -> None:
        """Show a single tool-use panel (legacy — prefer record_action)."""
        content = Text(f"Tool: {name}")
        if input_preview:
            content.append(f"\n{input_preview[:200]}", style="dim")
        self.console.print(Panel(content, border_style="yellow"))

    # ── Utility ─────────────────────────────────────────────────────

    def abort_notice(self) -> None:
        """Inform the user the current operation was aborted."""
        self.console.print(Text("  ⚠  Aborted by user", style="bold yellow"))

    def error(self, message: str) -> None:
        """Display an error message."""
        self.console.print(Text(f"  Error: {message}", style="bold red"))

    def info(self, message: str) -> None:
        """Display an info message."""
        self.console.print(Text(f"  {message}", style="dim italic"))

    def no_speech(self) -> None:
        """Indicate no speech was detected."""
        self.info("No speech detected — try again")

    def separator(self) -> None:
        """Print a visual separator."""
        self.console.print("─" * 60, style="dim")
