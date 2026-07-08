"""Seletor de emojis para o ícone de um atalho.

Janela com campo de busca e uma grade de emojis (renderizados em cores via
Pillow, para ficarem consistentes com o que aparece na barra). Ao escolher um
emoji, chama ``on_pick(char)``.
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from . import icons
from .emoji_data import EMOJI_GROUPS, EMOJIS
from .tooltip import ToolTip

_COLUMNS = 8
_CELL = 42
_IMG = 26


class EmojiPicker(ctk.CTkToplevel):
    """Grade de emojis com busca."""

    def __init__(self, master, dock, on_pick: Callable[[str], None]) -> None:
        super().__init__(master)
        self.dock = dock
        self._on_pick = on_pick

        self.title("Escolher emoji")
        self.geometry("420x520")
        self.minsize(360, 420)
        self.configure(fg_color=("#f3f4f6", "#1a1b1e"))
        self.attributes("-topmost", True)
        self.after(20, self._center)
        self.after(40, self._focus_search)
        if dock is not None:
            dock.register_dialog(self)

        # busca
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(12, 6))
        self._search = ctk.CTkEntry(top, placeholder_text="Buscar emoji (ex.: pasta, foguete, config)…")
        self._search.pack(fill="x")
        self._search.bind("<KeyRelease>", lambda _e: self._render())
        self._search.bind("<Escape>", lambda _e: self.destroy())

        # grade rolável
        self._grid = ctk.CTkScrollableFrame(self, fg_color=("#e9eaee", "#232427"))
        self._grid.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        self._render()

    # ------------------------------------------------------------------ #
    def _center(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"+{x}+{y}")

    def _focus_search(self) -> None:
        try:
            self._search.focus_force()
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ #
    def _render(self) -> None:
        for child in self._grid.winfo_children():
            child.destroy()

        query = self._search.get().strip().lower()
        row = 0
        if query:
            matches = [(e, kw) for (e, kw) in EMOJIS if query in kw or query in e]
            if not matches:
                ctk.CTkLabel(self._grid, text="Nenhum emoji encontrado",
                             text_color="gray").grid(row=0, column=0, columnspan=_COLUMNS, pady=16)
                return
            row = self._add_buttons(matches, row)
        else:
            # sem busca: mostra por seções
            for title, items in EMOJI_GROUPS:
                ctk.CTkLabel(self._grid, text=title, anchor="w",
                             font=ctk.CTkFont(size=12, weight="bold")).grid(
                    row=row, column=0, columnspan=_COLUMNS, sticky="w", padx=4, pady=(8, 2))
                row += 1
                row = self._add_buttons(items, row)

    def _add_buttons(self, items, row: int) -> int:
        col = 0
        for emoji, keywords in items:
            btn = ctk.CTkButton(
                self._grid,
                text="",
                image=icons.get_emoji_image(emoji, _IMG),
                width=_CELL,
                height=_CELL,
                corner_radius=8,
                fg_color="transparent",
                hover_color=("#dfe1e6", "#3a3d44"),
                command=lambda e=emoji: self._pick(e),
            )
            btn.grid(row=row, column=col, padx=2, pady=2)
            ToolTip(btn, keywords.split()[0] if keywords else emoji)
            col += 1
            if col >= _COLUMNS:
                col = 0
                row += 1
        return row + (1 if col else 0)

    def _pick(self, emoji: str) -> None:
        self._on_pick(emoji)
        self.destroy()
