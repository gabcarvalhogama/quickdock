"""Busca rápida de atalhos.

Uma sobreposição (overlay) leve que abre no centro da tela, com um campo de
texto e uma lista de resultados filtrada em tempo real.  Atalhos de teclado:

- Digitar     -> filtra pelos nomes/dicas.
- ↑ / ↓       -> navega entre os resultados.
- Enter       -> executa o resultado selecionado.
- Esc         -> fecha.
"""

from __future__ import annotations

import tkinter as tk
from typing import Callable, List, Tuple

import customtkinter as ctk

from . import icons
from .models import ACTION_GROUP, Shortcut

_TRANSPARENT_KEY = "#000002"


class SearchOverlay(ctk.CTkToplevel):
    """Sobreposição de busca rápida.

    A lista é "achatada": inclui os atalhos do topo e também os sub-botões
    dentro de grupos (com o caminho no nome, ex.: ``Dev ▸ VS Code``), para que
    seja possível encontrar e executar um sub-botão diretamente.
    """

    def __init__(self, dock, shortcuts: List[Shortcut], on_run: Callable[..., None]) -> None:
        super().__init__(dock)
        self.dock = dock
        self._on_run = on_run
        # lista de tuplas (atalho, nome_exibido)
        self._all: List[Tuple[Shortcut, str]] = self._flatten(shortcuts)
        self._filtered: List[Tuple[Shortcut, str]] = []
        self._selected = 0

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.configure(fg_color=_TRANSPARENT_KEY)
            self.attributes("-transparentcolor", _TRANSPARENT_KEY)
        except tk.TclError:
            pass
        dock.register_dialog(self)

        container = ctk.CTkFrame(self, corner_radius=16, fg_color=("#ffffff", "#202124"),
                                 border_width=1, border_color=("#d6d8dd", "#3a3d44"))
        container.pack(fill="both", expand=True, padx=2, pady=2)

        self._entry = ctk.CTkEntry(
            container, placeholder_text="Buscar atalho…",
            height=42, font=ctk.CTkFont(size=16), border_width=0,
        )
        self._entry.pack(fill="x", padx=12, pady=(12, 6))
        self._entry.bind("<KeyRelease>", self._on_key)
        self._entry.bind("<Down>", lambda _e: self._move_selection(1))
        self._entry.bind("<Up>", lambda _e: self._move_selection(-1))
        self._entry.bind("<Return>", lambda _e: self._run_selected())
        self._entry.bind("<Escape>", lambda _e: self.destroy())

        self._results = ctk.CTkScrollableFrame(container, fg_color="transparent", height=280)
        self._results.pack(fill="both", expand=True, padx=8, pady=(0, 10))

        self.geometry("420x360")
        self.after(10, self._center)
        self.after(40, self._entry.focus_force)
        self._apply_filter("")

    # ------------------------------------------------------------------ #
    def _center(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"+{x}+{y}")

    def _on_key(self, event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape"):
            return
        self._apply_filter(self._entry.get())

    @staticmethod
    def _flatten(shortcuts: List[Shortcut], prefix: str = "") -> List[Tuple[Shortcut, str]]:
        """Achata a árvore em pares (atalho, nome_com_caminho)."""
        out: List[Tuple[Shortcut, str]] = []
        for s in shortcuts:
            display = f"{prefix}{s.name}"
            out.append((s, display))
            if s.type == ACTION_GROUP and s.children:
                out.extend(SearchOverlay._flatten(s.children, prefix=f"{display} ▸ "))
        return out

    def _apply_filter(self, query: str) -> None:
        q = query.strip().lower()
        if q:
            self._filtered = [
                (s, disp) for (s, disp) in self._all
                if q in disp.lower() or q in s.tooltip.lower()
            ]
        else:
            self._filtered = list(self._all)
        self._selected = 0
        self._render()

    def _render(self) -> None:
        for child in self._results.winfo_children():
            child.destroy()

        if not self._filtered:
            ctk.CTkLabel(self._results, text="Nenhum resultado", text_color="gray").pack(pady=20)
            return

        for i, (shortcut, display) in enumerate(self._filtered):
            selected = i == self._selected
            suffix = "  ▸" if shortcut.type == ACTION_GROUP else ""
            btn = ctk.CTkButton(
                self._results,
                text=f"  {display}{suffix}",
                image=icons.get_icon(shortcut, 24),
                anchor="w",
                height=40,
                corner_radius=8,
                fg_color=("#e8eaed", "#34363b") if selected else "transparent",
                hover_color=("#e0e2e6", "#3a3d44"),
                text_color=("#1a1a1a", "#f0f0f0"),
                font=ctk.CTkFont(size=13),
                command=lambda s=shortcut: self._run(s),
            )
            btn.pack(fill="x", pady=2)

    def _move_selection(self, delta: int) -> None:
        if not self._filtered:
            return
        self._selected = (self._selected + delta) % len(self._filtered)
        self._render()

    def _run_selected(self) -> None:
        if self._filtered:
            self._run(self._filtered[self._selected][0])

    def _run(self, shortcut: Shortcut) -> None:
        self.destroy()
        self._on_run(shortcut)
