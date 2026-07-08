"""Tela de configurações do QuickDock.

Possui duas abas:

- **Atalhos** — lista os atalhos com reordenação por *drag and drop* (além de
  setas ▲▼), e botões para adicionar, editar e excluir.
- **Geral**  — orientação, tema, transparência, tamanho dos botões, bordas,
  rótulos, esconder automaticamente, bloquear posição, fixar na borda e o
  atalho global de teclado.

A janela é não-modal: aplica as mudanças imediatamente na barra através de
métodos do :class:`~quickdock.dock.Dock`.
"""

from __future__ import annotations

from tkinter import messagebox
from typing import List, Optional

import customtkinter as ctk

from . import icons
from .models import ACTION_GROUP, ACTION_LABELS, Settings, Shortcut


class SettingsWindow(ctk.CTkToplevel):
    """Janela de configurações."""

    def __init__(self, dock) -> None:
        super().__init__(dock)
        self.dock = dock

        self.title("QuickDock — Configurações")
        self.geometry("640x600")
        self.minsize(560, 480)
        self.configure(fg_color=("#f3f4f6", "#1a1b1e"))
        self.attributes("-topmost", True)
        self.after(30, self.focus_force)
        dock.register_dialog(self)

        # estado do drag and drop
        self._drag_index: Optional[int] = None
        self._rows: List[tuple] = []  # (frame, shortcut)

        self._tabs = ctk.CTkTabview(self)
        self._tabs.pack(fill="both", expand=True, padx=12, pady=12)
        self._tab_shortcuts = self._tabs.add("Atalhos")
        self._tab_general = self._tabs.add("Geral")

        self._build_shortcuts_tab()
        self._build_general_tab()

    # ================================================================== #
    # Aba: Atalhos
    # ================================================================== #
    def _build_shortcuts_tab(self) -> None:
        top = ctk.CTkFrame(self._tab_shortcuts, fg_color="transparent")
        top.pack(fill="x", pady=(4, 8))
        ctk.CTkLabel(
            top, text="Arraste pela alça ⠿ para reordenar", text_color="gray"
        ).pack(side="left")
        ctk.CTkButton(top, text="＋ Adicionar", width=130,
                      command=self._add_shortcut).pack(side="right")

        self._list = ctk.CTkScrollableFrame(self._tab_shortcuts, fg_color=("#e9eaee", "#232427"))
        self._list.pack(fill="both", expand=True)
        self.refresh_list()

    def refresh_list(self) -> None:
        """Redesenha a lista de atalhos (chamada após qualquer alteração)."""
        for child in self._list.winfo_children():
            child.destroy()
        self._rows = []

        if not self.dock.shortcuts:
            ctk.CTkLabel(self._list, text="Nenhum atalho ainda.", text_color="gray").pack(pady=20)
            return

        for index, shortcut in enumerate(self.dock.shortcuts):
            self._build_row(index, shortcut)

    def _build_row(self, index: int, shortcut: Shortcut) -> None:
        row = ctk.CTkFrame(self._list, fg_color=("#f3f4f6", "#2b2c30"), corner_radius=8)
        row.pack(fill="x", pady=3, padx=2)
        self._rows.append((row, shortcut))

        # alça de arrastar
        grip = ctk.CTkLabel(row, text="⠿", width=24, cursor="fleur",
                            text_color="gray")
        grip.pack(side="left", padx=(6, 2))
        grip.bind("<ButtonPress-1>", lambda e, i=index: self._drag_start(i))
        grip.bind("<ButtonRelease-1>", self._drag_release)

        # ícone
        img = icons.get_icon(shortcut, 26)
        ctk.CTkLabel(row, image=img, text="", width=30).pack(side="left")

        # nome + tipo
        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ctk.CTkLabel(info, text=shortcut.name, anchor="w",
                     font=ctk.CTkFont(size=13, weight="bold")).pack(fill="x")
        subtitle = ACTION_LABELS.get(shortcut.type, shortcut.type)
        if shortcut.type == ACTION_GROUP:
            subtitle += f" · {len(shortcut.children)} sub-botões"
        ctk.CTkLabel(info, text=subtitle,
                     anchor="w", text_color="gray",
                     font=ctk.CTkFont(size=11)).pack(fill="x")

        # ações
        ctk.CTkButton(row, text="✕", width=32, fg_color="transparent",
                      hover_color="#c0392b",
                      command=lambda s=shortcut: self._delete_shortcut(s)).pack(side="right", padx=(0, 6))
        ctk.CTkButton(row, text="✎", width=32, fg_color="transparent", hover_color="gray40",
                      command=lambda s=shortcut: self._edit_shortcut(s)).pack(side="right")
        ctk.CTkButton(row, text="▼", width=28, fg_color="transparent", hover_color="gray40",
                      command=lambda i=index: self._move(i, 1)).pack(side="right")
        ctk.CTkButton(row, text="▲", width=28, fg_color="transparent", hover_color="gray40",
                      command=lambda i=index: self._move(i, -1)).pack(side="right")

    # --- drag and drop -------------------------------------------------- #
    def _drag_start(self, index: int) -> None:
        self._drag_index = index

    def _drag_release(self, event) -> None:
        if self._drag_index is None:
            return
        target = self._drop_index(event.y_root)
        src = self._drag_index
        self._drag_index = None
        if target is None or target == src:
            return
        items = self.dock.shortcuts
        item = items.pop(src)
        if target > src:
            target -= 1
        items.insert(max(0, min(target, len(items))), item)
        self.dock.set_shortcuts(items)
        self.refresh_list()

    def _drop_index(self, y_root: int) -> Optional[int]:
        """Índice de destino a partir da posição vertical do ponteiro."""
        for i, (frame, _s) in enumerate(self._rows):
            if not frame.winfo_exists():
                continue
            top = frame.winfo_rooty()
            mid = top + frame.winfo_height() / 2
            if y_root < mid:
                return i
        return len(self._rows)

    # --- setas ---------------------------------------------------------- #
    def _move(self, index: int, delta: int) -> None:
        items = self.dock.shortcuts
        j = index + delta
        if 0 <= j < len(items):
            items[index], items[j] = items[j], items[index]
            self.dock.set_shortcuts(items)
            self.refresh_list()

    # --- CRUD ----------------------------------------------------------- #
    def _add_shortcut(self) -> None:
        from .editor import ShortcutEditor

        def on_save(result: Shortcut) -> None:
            self.dock.shortcuts.append(result)
            self.dock.set_shortcuts(self.dock.shortcuts)
            self.refresh_list()

        ShortcutEditor(self, self.dock, None, on_save)

    def _edit_shortcut(self, shortcut: Shortcut) -> None:
        from .editor import ShortcutEditor

        def on_save(result: Shortcut) -> None:
            idx = self.dock._index_of(shortcut.id)
            if idx >= 0:
                self.dock.shortcuts[idx] = result
            self.dock.set_shortcuts(self.dock.shortcuts)
            self.refresh_list()

        ShortcutEditor(self, self.dock, shortcut, on_save)

    def _delete_shortcut(self, shortcut: Shortcut) -> None:
        if not messagebox.askyesno("QuickDock", f"Excluir “{shortcut.name}”?", parent=self):
            return
        self.dock.shortcuts = [s for s in self.dock.shortcuts if s.id != shortcut.id]
        self.dock.set_shortcuts(self.dock.shortcuts)
        self.refresh_list()

    # ================================================================== #
    # Aba: Geral
    # ================================================================== #
    def _build_general_tab(self) -> None:
        s: Settings = self.dock.settings
        body = ctk.CTkScrollableFrame(self._tab_general, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # Orientação
        self._section(body, "Orientação")
        orient = ctk.CTkSegmentedButton(
            body, values=["Vertical", "Horizontal"],
            command=lambda v: self.dock._set_orientation(
                "vertical" if v == "Vertical" else "horizontal"),
        )
        orient.set("Vertical" if s.orientation == "vertical" else "Horizontal")
        orient.pack(fill="x", pady=(0, 6))

        # Fixar na borda
        self._section(body, "Fixar na borda")
        pin = ctk.CTkOptionMenu(
            body,
            values=["Nenhuma", "Esquerda", "Direita", "Topo", "Base"],
            command=self._on_pin_change,
        )
        pin.set({"none": "Nenhuma", "left": "Esquerda", "right": "Direita",
                 "top": "Topo", "bottom": "Base"}.get(s.pinned_side, "Nenhuma"))
        pin.pack(fill="x", pady=(0, 6))

        # Tema
        self._section(body, "Tema")
        theme = ctk.CTkSegmentedButton(
            body, values=["Escuro", "Claro", "Sistema"],
            command=lambda v: self.dock._set_theme(
                {"Escuro": "dark", "Claro": "light", "Sistema": "system"}[v]),
        )
        theme.set({"dark": "Escuro", "light": "Claro", "system": "Sistema"}.get(s.theme, "Escuro"))
        theme.pack(fill="x", pady=(0, 6))

        # Transparência
        self._opacity_label = self._section(body, f"Transparência — {int(s.opacity * 100)}%")
        opacity = ctk.CTkSlider(body, from_=0.3, to=1.0, command=self._on_opacity)
        opacity.set(s.opacity)
        opacity.pack(fill="x", pady=(0, 6))

        # Tamanho dos botões
        self._size_label = self._section(body, f"Tamanho dos botões — {s.button_size}px")
        size = ctk.CTkSlider(body, from_=32, to=64, number_of_steps=32, command=self._on_size_preview)
        size.set(s.button_size)
        size.bind("<ButtonRelease-1>", lambda _e: self._apply_size(size.get()))
        size.pack(fill="x", pady=(0, 6))

        # Bordas arredondadas
        self._radius_label = self._section(body, f"Bordas arredondadas — {s.corner_radius}px")
        radius = ctk.CTkSlider(body, from_=0, to=40, number_of_steps=40, command=self._on_radius_preview)
        radius.set(s.corner_radius)
        radius.bind("<ButtonRelease-1>", lambda _e: self._apply_radius(radius.get()))
        radius.pack(fill="x", pady=(0, 10))

        # Rótulo dos botões (nome)
        self._section(body, "Nome dos botões")
        labels = ctk.CTkSegmentedButton(
            body, values=["Oculto", "Ao lado", "Embaixo"], command=self._on_label_pos)
        labels.set({"none": "Oculto", "side": "Ao lado", "below": "Embaixo"}
                   .get(s.label_position, "Oculto"))
        labels.pack(fill="x", pady=(0, 8))

        # Switches
        self._switch(body, "Sempre no topo", s.always_on_top, self._on_topmost)
        self._switch(body, "Bloquear posição", s.locked, self._on_lock)
        self._switch(body, "Esconder automaticamente na borda", s.auto_hide, self._on_autohide)

        # Atalho global
        self._section(body, "Atalho global (mostrar/esconder)")
        hk_row = ctk.CTkFrame(body, fg_color="transparent")
        hk_row.pack(fill="x")
        self._hotkey_entry = ctk.CTkEntry(hk_row)
        self._hotkey_entry.insert(0, s.hotkey)
        self._hotkey_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(hk_row, text="Aplicar", width=90,
                      command=self._apply_hotkey).pack(side="left", padx=(6, 0))
        self._hotkey_status = ctk.CTkLabel(body, text=self._hotkey_status_text(), text_color="gray")
        self._hotkey_status.pack(fill="x", pady=(4, 0))

    # --- construtores de seção ----------------------------------------- #
    def _section(self, master, title: str) -> ctk.CTkLabel:
        lbl = ctk.CTkLabel(master, text=title, anchor="w",
                           font=ctk.CTkFont(size=13, weight="bold"))
        lbl.pack(fill="x", pady=(12, 4))
        return lbl

    def _switch(self, master, text: str, value: bool, command) -> None:
        sw = ctk.CTkSwitch(master, text=text, command=lambda: command(bool(sw.get())))
        sw.pack(anchor="w", pady=6)
        if value:
            sw.select()

    # --- handlers ------------------------------------------------------- #
    def _on_pin_change(self, value: str) -> None:
        self.dock._set_pinned(
            {"Nenhuma": "none", "Esquerda": "left", "Direita": "right",
             "Topo": "top", "Base": "bottom"}[value])

    def _on_opacity(self, value: float) -> None:
        self.dock._set_opacity(round(float(value), 2))
        self._opacity_label.configure(text=f"Transparência — {int(value * 100)}%")

    def _on_size_preview(self, value: float) -> None:
        self._size_label.configure(text=f"Tamanho dos botões — {int(value)}px")

    def _apply_size(self, value: float) -> None:
        self.dock.settings.button_size = int(value)
        from . import storage
        storage.save_settings(self.dock.settings)
        self.dock.rebuild()

    def _on_radius_preview(self, value: float) -> None:
        self._radius_label.configure(text=f"Bordas arredondadas — {int(value)}px")

    def _apply_radius(self, value: float) -> None:
        self.dock.settings.corner_radius = int(value)
        from . import storage
        storage.save_settings(self.dock.settings)
        self.dock.rebuild()

    def _on_label_pos(self, value: str) -> None:
        self.dock.settings.label_position = {
            "Oculto": "none", "Ao lado": "side", "Embaixo": "below"}[value]
        from . import storage
        storage.save_settings(self.dock.settings)
        self.dock.rebuild()

    def _on_topmost(self, value: bool) -> None:
        self.dock.settings.always_on_top = value
        self.dock.attributes("-topmost", value)
        from . import storage
        storage.save_settings(self.dock.settings)

    def _on_lock(self, value: bool) -> None:
        self.dock.settings.locked = value
        from . import storage
        storage.save_settings(self.dock.settings)

    def _on_autohide(self, value: bool) -> None:
        self.dock.settings.auto_hide = value
        if not value:
            self.dock._hidden_by_autohide = False
            self.dock._apply_geometry()
        from . import storage
        storage.save_settings(self.dock.settings)

    def _apply_hotkey(self) -> None:
        hotkey = self._hotkey_entry.get().strip().lower()
        if not hotkey:
            return
        self.dock.settings.hotkey = hotkey
        from . import storage
        storage.save_settings(self.dock.settings)
        self.dock._restart_hotkey()
        self._hotkey_status.configure(text=self._hotkey_status_text())

    def _hotkey_status_text(self) -> str:
        hk = self.dock.hotkeys
        if not hk.available:
            return "⚠ Biblioteca 'keyboard' indisponível — atalho global desativado."
        if hk.last_error:
            return f"⚠ Não foi possível registrar: {hk.last_error}"
        return f"✓ Ativo: {self.dock.settings.hotkey}"
