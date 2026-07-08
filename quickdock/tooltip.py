"""Dica de contexto (tooltip) exibida ao passar o mouse.

Implementação leve baseada em uma ``Toplevel`` sem borda, compatível com
widgets do CustomTkinter.  A dica aparece após um pequeno atraso e some
quando o ponteiro sai do widget.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Optional, Union


class ToolTip:
    """Anexa uma dica textual a um widget."""

    def __init__(
        self,
        widget: tk.Widget,
        text: Union[str, Callable[[], str]] = "",
        delay: int = 450,
    ) -> None:
        self.widget = widget
        self._text = text
        self.delay = delay
        self._after_id: Optional[str] = None
        self._tip: Optional[tk.Toplevel] = None

        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    # ------------------------------------------------------------------ #
    def set_text(self, text: Union[str, Callable[[], str]]) -> None:
        self._text = text

    def _resolve_text(self) -> str:
        return self._text() if callable(self._text) else self._text

    # ------------------------------------------------------------------ #
    def _schedule(self, _event=None) -> None:
        self._cancel()
        self._after_id = self.widget.after(self.delay, self._show)

    def _show(self) -> None:
        text = self._resolve_text()
        if not text or self._tip is not None:
            return
        # posiciona logo abaixo/à direita do ponteiro
        x = self.widget.winfo_pointerx() + 14
        y = self.widget.winfo_pointery() + 18

        self._tip = tk.Toplevel(self.widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_attributes("-topmost", True)
        try:
            self._tip.wm_attributes("-alpha", 0.96)
        except tk.TclError:
            pass
        self._tip.configure(background="#111214")

        label = tk.Label(
            self._tip,
            text=text,
            justify="left",
            background="#111214",
            foreground="#f2f2f2",
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
            borderwidth=0,
        )
        label.pack()
        self._tip.wm_geometry(f"+{x}+{y}")

    def _hide(self, _event=None) -> None:
        self._cancel()
        if self._tip is not None:
            self._tip.destroy()
            self._tip = None

    def _cancel(self) -> None:
        if self._after_id is not None:
            try:
                self.widget.after_cancel(self._after_id)
            except (ValueError, tk.TclError):
                pass
            self._after_id = None
