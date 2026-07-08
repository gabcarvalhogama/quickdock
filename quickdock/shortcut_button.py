"""Widget de um botão de atalho na barra.

Encapsula um ``CTkButton`` com ícone, rótulo opcional e dica (tooltip).
- Clique esquerdo  -> executa a ação.
- Clique direito   -> abre o editor daquele atalho (callback).
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk

from . import icons
from .models import ACTION_GROUP, Shortcut
from .tooltip import ToolTip


class ShortcutButton(ctk.CTkButton):
    """Botão que representa um atalho no dock."""

    def __init__(
        self,
        master,
        shortcut: Shortcut,
        size: int,
        label_position: str,   # "none" | "side" | "below"
        on_click: Callable[..., None],
        on_edit: Callable[[Shortcut], None],
        **kwargs,
    ) -> None:
        self.shortcut = shortcut
        self._on_click = on_click
        self._on_edit = on_edit

        is_group = shortcut.type == ACTION_GROUP
        chevron = "  ▸" if is_group else ""

        if label_position == "side":
            icon_px = int(size * 0.58)
            width = max(size, 132)
            text = f"{shortcut.name}{chevron}"
            anchor, compound, height = "w", "left", size
            font = ctk.CTkFont(size=12)
        elif label_position == "below":
            # nome bem pequeno embaixo do ícone
            icon_px = int(size * 0.52)
            width = max(size, 62)
            name = shortcut.name
            if len(name) > 12:
                name = name[:11] + "…"
            text = f"{name}{'  ▸' if is_group else ''}"
            anchor, compound, height = "center", "top", size + 15
            font = ctk.CTkFont(size=9)
        else:  # "none" -> só ícone
            icon_px = int(size * 0.58)
            width = size
            text = ""
            anchor, compound, height = "center", "left", size
            font = ctk.CTkFont(size=12)

        image = icons.get_icon(shortcut, icon_px)

        super().__init__(
            master,
            image=image,
            text=text,
            width=width,
            height=height,
            corner_radius=int(size * 0.28),
            fg_color="transparent",
            hover_color=("#e2e5ea", "#3a3d44"),
            text_color=("#1a1a1a", "#f0f0f0"),
            anchor=anchor,
            compound=compound,
            font=font,
            command=self._handle_click,
            **kwargs,
        )

        # clique direito -> editar
        self.bind("<Button-3>", self._handle_right_click, add="+")

        # tooltip (só faz sentido quando não há rótulo visível)
        self._tooltip = ToolTip(self, shortcut.tooltip_text)

    # ------------------------------------------------------------------ #
    def _handle_click(self) -> None:
        # passa o próprio botão como âncora (usado por grupos para posicionar
        # o painel de sub-botões ao lado do botão clicado)
        self._on_click(self.shortcut, self)

    def _handle_right_click(self, _event=None) -> None:
        self._on_edit(self.shortcut)
