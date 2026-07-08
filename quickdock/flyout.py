"""Painel de sub-botões (flyout) de um grupo.

Quando um atalho do tipo ``group`` é clicado, abre-se um painel flutuante ao
lado do botão, listando os atalhos filhos. Cada filho pode ser executado
diretamente; se o filho também for um grupo, um novo painel é aberto ao lado
dele (aninhamento em cascata).

O gerenciamento de abrir/fechar/posicionar em cascata fica no
:class:`~quickdock.dock.Dock`; aqui cuidamos apenas da janela e do layout.
"""

from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from .models import Shortcut
from .shortcut_button import ShortcutButton

# cor-chave para cantos arredondados transparentes (única por janela)
_TRANSPARENT_KEY = "#000003"

# limite de itens antes de usar rolagem, para não passar da tela
_SCROLL_THRESHOLD = 12


class Flyout(ctk.CTkToplevel):
    """Janela com os sub-botões de um grupo."""

    def __init__(self, dock, group: Shortcut, anchor, level: int) -> None:
        super().__init__(dock)
        self.dock = dock
        self.group = group
        self.level = level

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            self.attributes("-alpha", dock.settings.opacity)
            self.configure(fg_color=_TRANSPARENT_KEY)
            self.attributes("-transparentcolor", _TRANSPARENT_KEY)
        except tk.TclError:
            pass

        container = ctk.CTkFrame(
            self,
            corner_radius=max(10, dock.settings.corner_radius - 4),
            fg_color=("#f3f4f6", "#232427"),
            border_width=1,
            border_color=("#d6d8dd", "#3a3d44"),
        )
        container.pack(fill="both", expand=True)

        self._build_items(container, group, dock)

        self.update_idletasks()
        self._place(anchor)

        self.bind("<Escape>", lambda _e: dock._close_flyouts())
        self.after(20, self._safe_focus)

    # ------------------------------------------------------------------ #
    def _build_items(self, container, group: Shortcut, dock) -> None:
        size = int(dock.settings.button_size * 0.86)

        if not group.children:
            ctk.CTkLabel(container, text="(grupo vazio)", text_color="gray").pack(
                padx=16, pady=12)
            return

        if len(group.children) > _SCROLL_THRESHOLD:
            inner = ctk.CTkScrollableFrame(container, fg_color="transparent",
                                           width=190, height=size * _SCROLL_THRESHOLD)
        else:
            inner = ctk.CTkFrame(container, fg_color="transparent")
        inner.pack(padx=6, pady=6, fill="both", expand=True)

        for child in group.children:
            btn = ShortcutButton(
                inner,
                shortcut=child,
                size=size,
                label_position="side",  # painel sempre com nome ao lado (menu)
                on_click=dock._flyout_child_clicked,  # (child, button)
                on_edit=lambda _s: None,               # edição é feita nas configs
            )
            btn.pack(fill="x", pady=2)

    # ------------------------------------------------------------------ #
    def _safe_focus(self) -> None:
        try:
            self.focus_force()
        except tk.TclError:
            pass

    def _place(self, anchor) -> None:
        """Posiciona o painel ao lado do botão-âncora, dentro da tela."""
        self.update_idletasks()
        fw = self.winfo_reqwidth() or self.winfo_width()
        fh = self.winfo_reqheight() or self.winfo_height()
        try:
            ax, ay = anchor.winfo_rootx(), anchor.winfo_rooty()
            aw, ah = anchor.winfo_width(), anchor.winfo_height()
        except tk.TclError:
            ax = ay = 100
            aw = ah = 40
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        gap = 6

        if self.dock.settings.orientation == "vertical":
            # abre para o lado com mais espaço
            if ax + aw / 2 > sw / 2:
                x = ax - fw - gap
            else:
                x = ax + aw + gap
            y = ay
        else:
            if ay + ah / 2 > sh / 2:
                y = ay - fh - gap
            else:
                y = ay + ah + gap
            x = ax

        x = int(max(2, min(x, sw - fw - 2)))
        y = int(max(2, min(y, sh - fh - 2)))
        self.geometry(f"{fw}x{fh}+{x}+{y}")
