"""Janela principal do QuickDock — a barra de atalhos.

Reúne a interface (barra sempre visível, arrastável, com bordas arredondadas)
e toda a interação: menu de contexto, orientação, fixar na borda, esconder
automaticamente, transparência, tema, bloqueio de posição, animação de
abertura, atalho global e busca rápida.

A lógica de execução das ações fica em :mod:`quickdock.actions`; a persistência
em :mod:`quickdock.storage`.  Esta classe orquestra o estado e a apresentação.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox
from typing import List, Optional

import customtkinter as ctk

from . import autostart, icons, storage
from .actions import ActionExecutor
from .hotkeys import HotkeyManager
from .models import ACTION_GROUP, Settings, Shortcut
from .shortcut_button import ShortcutButton
from .tray import TrayIcon

# Cor "chave" para transparência das bordas arredondadas.  É improvável de
# aparecer em qualquer conteúdo visível, evitando halos coloridos.
_TRANSPARENT_KEY = "#000001"

_OPACITY_STEPS = [1.0, 0.9, 0.8, 0.7, 0.55]
_TICK_MS = 120  # frequência do loop de manutenção (hotkey, topmost, auto-hide)


class Dock(ctk.CTk):
    """A barra de atalhos flutuante."""

    def __init__(self) -> None:
        super().__init__()

        # --- estado -------------------------------------------------------
        self.settings: Settings = storage.load_settings()
        self.shortcuts: List[Shortcut] = storage.load_shortcuts()
        self.executor = ActionExecutor(on_error=self._show_error)
        self.hotkeys = HotkeyManager()
        self.tray = TrayIcon()

        self._container: Optional[ctk.CTkFrame] = None
        self._drag_offset = (0, 0)
        self._dragging = False
        self._visible = True
        self._hidden_by_autohide = False
        self._anim_job: Optional[str] = None
        self._settings_window = None  # referência viva para a tela de config
        self._search_window = None
        self._win_w = 0
        self._win_h = 0
        self._open_dialogs = 0  # nº de diálogos abertos (suspende reafirmação de topo)

        # --- estado dos painéis de sub-botões (flyouts) -------------------
        self._flyouts: List = []          # cadeia de painéis abertos
        self._flyout_root_id = None       # id do grupo raiz aberto (para alternar)
        self._flyout_anchor = None        # botão do dock que abriu a cadeia
        self._flyout_polling = False
        self._flyout_miss = 0

        # --- aparência ----------------------------------------------------
        ctk.set_appearance_mode(self._ctk_mode(self.settings.theme))
        ctk.set_default_color_theme("blue")

        self.title("QuickDock")
        self.overrideredirect(True)  # sem barra de título -> discreto
        # esconde durante a montagem: evita "piscar" e permite aplicar o
        # estilo de janela-ferramenta antes da primeira exibição
        self.withdraw()
        self._apply_window_attributes()

        # cor de fundo da janela = cor-chave -> cantos ficam transparentes
        try:
            self.configure(fg_color=_TRANSPARENT_KEY)
            self.attributes("-transparentcolor", _TRANSPARENT_KEY)
        except tk.TclError:
            pass  # sem transparência: degrada para cantos retos

        self._build()
        self._apply_geometry()
        self._hide_from_taskbar()  # roda em segundo plano, sem botão na barra
        self._start_hotkey()
        self._start_tray()

        # loop de manutenção de baixo custo
        self.after(_TICK_MS, self._tick)
        # salva a posição/estado ao fechar
        self.protocol("WM_DELETE_WINDOW", self.quit_app)

        # exibe a barra (a menos que o usuário queira iniciar só na bandeja)
        if self.settings.start_hidden and self.tray.available:
            self._visible = False
        else:
            self.deiconify()
            self._animate_in()

    # ================================================================== #
    # Construção da interface
    # ================================================================== #
    def _build(self) -> None:
        """(Re)constrói o conteúdo do dock conforme a orientação atual."""
        if self._container is not None:
            self._container.destroy()

        vertical = self.settings.orientation == "vertical"
        pad = 6

        self._container = ctk.CTkFrame(
            self,
            corner_radius=self.settings.corner_radius,
            fg_color=("#f3f4f6", "#1e1f22"),
            border_width=1,
            border_color=("#d6d8dd", "#303236"),
        )
        self._container.pack(fill="both", expand=True)

        side = "top" if vertical else "left"
        fill = "x" if vertical else "y"

        # área interna com um respiro
        inner = ctk.CTkFrame(self._container, fg_color="transparent")
        inner.pack(padx=pad, pady=pad, fill="both", expand=True)

        # 1) alça de arrastar
        grip = ctk.CTkLabel(
            inner,
            text="⠿⠿" if not vertical else "⠿",
            font=ctk.CTkFont(size=13),
            text_color=("#9aa0a6", "#7a7f87"),
            cursor="fleur",
        )
        grip.pack(side=side, fill=fill, pady=(0, 2) if vertical else 0,
                  padx=0 if vertical else (0, 2))
        self._bind_drag(grip)
        grip.bind("<Button-3>", self._popup_menu, add="+")

        # 2) botões de atalho
        for shortcut in self.shortcuts:
            btn = ShortcutButton(
                inner,
                shortcut=shortcut,
                size=self.settings.button_size,
                label_position=self.settings.label_position,
                on_click=self._run_shortcut,
                on_edit=self._edit_shortcut,
            )
            btn.pack(side=side, pady=2 if vertical else 0, padx=0 if vertical else 2)

        # 3) rodapé: busca, configurações, menu
        self._make_tool_button(inner, "⌕", side, "Busca rápida", self.open_search)
        self._make_tool_button(inner, "⚙", side, "Configurações", self.open_settings)
        self._make_tool_button(inner, "⋮", side, "Menu", self._popup_menu_event)

        self.update_idletasks()

    def _make_tool_button(self, master, symbol, side, tip, command) -> ShortcutButton:
        from .tooltip import ToolTip

        size = int(self.settings.button_size * 0.82)
        btn = ctk.CTkButton(
            master,
            text=symbol,
            width=size,
            height=size,
            corner_radius=int(size * 0.28),
            fg_color="transparent",
            hover_color=("#e2e5ea", "#3a3d44"),
            text_color=("#5f6368", "#9aa0a6"),
            font=ctk.CTkFont(size=15),
            command=command,
        )
        btn.pack(side=side, pady=2 if side == "top" else 0, padx=0 if side == "top" else 2)
        ToolTip(btn, tip)
        return btn

    # ================================================================== #
    # Geometria / posição
    # ================================================================== #
    def _apply_geometry(self) -> None:
        """Calcula e aplica tamanho + posição (livre ou fixado na borda)."""
        self.update_idletasks()
        w = self._container.winfo_reqwidth() if self._container else 120
        h = self._container.winfo_reqheight() if self._container else 200
        self._win_w, self._win_h = w, h

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        side = self.settings.pinned_side
        margin = 6

        if side == "left":
            x, y = margin, (sh - h) // 2
        elif side == "right":
            x, y = sw - w - margin, (sh - h) // 2
        elif side == "top":
            x, y = (sw - w) // 2, margin
        elif side == "bottom":
            x, y = (sw - w) // 2, sh - h - margin
        else:  # livre
            x = self.settings.pos_x if self.settings.pos_x is not None else sw - w - 40
            y = self.settings.pos_y if self.settings.pos_y is not None else (sh - h) // 2

        # mantém dentro da tela
        x = max(0, min(x, sw - w))
        y = max(0, min(y, sh - h))
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _save_position(self) -> None:
        self.settings.pos_x = self.winfo_x()
        self.settings.pos_y = self.winfo_y()
        storage.save_settings(self.settings)

    # ================================================================== #
    # Arrastar
    # ================================================================== #
    def _bind_drag(self, widget) -> None:
        widget.bind("<Button-1>", self._start_move, add="+")
        widget.bind("<B1-Motion>", self._on_move, add="+")
        widget.bind("<ButtonRelease-1>", self._stop_move, add="+")

    def _start_move(self, event) -> None:
        if self.settings.locked:
            return
        self._close_flyouts()
        self._dragging = True
        self._drag_offset = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _on_move(self, event) -> None:
        if not self._dragging or self.settings.locked:
            return
        x = event.x_root - self._drag_offset[0]
        y = event.y_root - self._drag_offset[1]
        self.geometry(f"+{x}+{y}")

    def _stop_move(self, _event=None) -> None:
        if not self._dragging:
            return
        self._dragging = False
        # arrastar manualmente "solta" da borda fixada
        if self.settings.pinned_side != "none":
            self.settings.pinned_side = "none"
        self._save_position()

    # ================================================================== #
    # Menu de contexto
    # ================================================================== #
    def _popup_menu_event(self) -> None:
        """Abre o menu a partir de um clique de botão (posição do ponteiro)."""
        self._show_menu(self.winfo_pointerx(), self.winfo_pointery())

    def _popup_menu(self, event) -> None:
        self._show_menu(event.x_root, event.y_root)

    def _show_menu(self, x: int, y: int) -> None:
        menu = tk.Menu(self, tearoff=0)

        menu.add_command(label="⚙  Configurações…", command=self.open_settings)
        menu.add_command(label="⌕  Busca rápida", command=self.open_search)
        menu.add_command(label="＋  Novo atalho", command=lambda: self._edit_shortcut(None))
        menu.add_separator()

        # orientação
        orient = tk.Menu(menu, tearoff=0)
        for value, label in (("vertical", "Vertical"), ("horizontal", "Horizontal")):
            orient.add_radiobutton(
                label=label,
                value=value,
                variable=tk.StringVar(value=self.settings.orientation),
                command=lambda v=value: self._set_orientation(v),
            )
        menu.add_cascade(label="Orientação", menu=orient)

        # fixar na borda
        pin = tk.Menu(menu, tearoff=0)
        for value, label in (
            ("none", "Nenhuma (livre)"),
            ("left", "Esquerda"),
            ("right", "Direita"),
            ("top", "Topo"),
            ("bottom", "Base"),
        ):
            pin.add_radiobutton(
                label=label,
                value=value,
                variable=tk.StringVar(value=self.settings.pinned_side),
                command=lambda v=value: self._set_pinned(v),
            )
        menu.add_cascade(label="Fixar na borda", menu=pin)

        menu.add_checkbutton(
            label="Esconder automaticamente",
            onvalue=1,
            offvalue=0,
            variable=tk.IntVar(value=int(self.settings.auto_hide)),
            command=self._toggle_autohide,
        )
        menu.add_checkbutton(
            label="Bloquear posição",
            variable=tk.IntVar(value=int(self.settings.locked)),
            command=self._toggle_lock,
        )
        menu.add_separator()

        # tema
        theme = tk.Menu(menu, tearoff=0)
        for value, label in (("dark", "Escuro"), ("light", "Claro"), ("system", "Sistema")):
            theme.add_radiobutton(
                label=label,
                value=value,
                variable=tk.StringVar(value=self.settings.theme),
                command=lambda v=value: self._set_theme(v),
            )
        menu.add_cascade(label="Tema", menu=theme)

        # transparência
        alpha = tk.Menu(menu, tearoff=0)
        for value in _OPACITY_STEPS:
            alpha.add_radiobutton(
                label=f"{int(value * 100)}%",
                value=value,
                variable=tk.DoubleVar(value=self.settings.opacity),
                command=lambda v=value: self._set_opacity(v),
            )
        menu.add_cascade(label="Transparência", menu=alpha)

        menu.add_checkbutton(
            label="Sempre no topo",
            variable=tk.IntVar(value=int(self.settings.always_on_top)),
            command=self._toggle_topmost,
        )
        menu.add_separator()

        # rodar em segundo plano (bandeja) e iniciar com o Windows
        menu.add_checkbutton(
            label="Iniciar escondido (bandeja)",
            variable=tk.IntVar(value=int(self.settings.start_hidden)),
            command=self._toggle_start_hidden,
            state="normal" if self.tray.available else "disabled",
        )
        menu.add_checkbutton(
            label="Iniciar com o Windows",
            variable=tk.IntVar(value=int(autostart.is_enabled())),
            command=self._toggle_autostart,
            state="normal" if autostart.available() else "disabled",
        )
        menu.add_separator()
        menu.add_command(label="Recarregar atalhos", command=self.reload_shortcuts)
        menu.add_command(label="Sair", command=self.quit_app)

        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    # ================================================================== #
    # Ações do menu / configurações
    # ================================================================== #
    def _set_orientation(self, value: str) -> None:
        self.settings.orientation = value
        storage.save_settings(self.settings)
        self.rebuild()

    def _set_pinned(self, value: str) -> None:
        self.settings.pinned_side = value
        if value in ("left", "right"):
            self.settings.orientation = "vertical"
        elif value in ("top", "bottom"):
            self.settings.orientation = "horizontal"
        storage.save_settings(self.settings)
        self._hidden_by_autohide = False
        self.rebuild()

    def _toggle_autohide(self) -> None:
        self.settings.auto_hide = not self.settings.auto_hide
        if not self.settings.auto_hide:
            self._hidden_by_autohide = False
            self._apply_geometry()
        storage.save_settings(self.settings)

    def _toggle_lock(self) -> None:
        self.settings.locked = not self.settings.locked
        storage.save_settings(self.settings)

    def _set_theme(self, value: str) -> None:
        self.settings.theme = value
        ctk.set_appearance_mode(self._ctk_mode(value))
        storage.save_settings(self.settings)

    def _set_opacity(self, value: float) -> None:
        self.settings.opacity = value
        self.attributes("-alpha", value)
        storage.save_settings(self.settings)

    def _toggle_topmost(self) -> None:
        self.settings.always_on_top = not self.settings.always_on_top
        self.attributes("-topmost", self.settings.always_on_top)
        storage.save_settings(self.settings)

    def _toggle_start_hidden(self) -> None:
        self.settings.start_hidden = not self.settings.start_hidden
        storage.save_settings(self.settings)

    def _toggle_autostart(self) -> None:
        if not autostart.set_enabled(not autostart.is_enabled()):
            self._show_error(
                "Não foi possível alterar o início automático com o Windows."
            )

    # ================================================================== #
    # Recarregar / aplicar mudanças externas (tela de configurações)
    # ================================================================== #
    def rebuild(self) -> None:
        """Reconstrói a barra e reaplica a geometria (após mudanças)."""
        self._close_flyouts()  # âncoras antigas serão destruídas
        icons.clear_cache()
        self._build()
        self._apply_geometry()

    def apply_settings(self, settings: Settings) -> None:
        """Aplica um novo objeto de configurações vindo da tela de config."""
        self.settings = settings
        storage.save_settings(self.settings)
        ctk.set_appearance_mode(self._ctk_mode(settings.theme))
        self._apply_window_attributes()
        self.rebuild()
        self._restart_hotkey()

    def reload_shortcuts(self) -> None:
        """Recarrega os atalhos do disco (útil após edição manual do JSON)."""
        self.shortcuts = storage.load_shortcuts()
        self.rebuild()

    def set_shortcuts(self, shortcuts: List[Shortcut]) -> None:
        """Substitui a lista de atalhos, persiste e redesenha."""
        self.shortcuts = shortcuts
        storage.save_shortcuts(self.shortcuts)
        self.rebuild()

    # ================================================================== #
    # Execução / edição de atalhos
    # ================================================================== #
    def _run_shortcut(self, shortcut: Shortcut, anchor=None) -> None:
        """Executa um atalho; se for um grupo, abre/fecha o painel de filhos."""
        if shortcut.type == ACTION_GROUP:
            # clicar de novo no mesmo grupo alterna (fecha)
            if self._flyouts and self._flyout_root_id == shortcut.id:
                self._close_flyouts()
                return
            self._flyout_anchor = anchor
            self.open_group(shortcut, anchor or self._container, level=0,
                            root_id=shortcut.id)
        else:
            self._close_flyouts()
            self.executor.execute(shortcut)

    # ------------------------------------------------------------------ #
    # Sub-botões (flyouts)
    # ------------------------------------------------------------------ #
    def open_group(self, group: Shortcut, anchor, level: int, root_id=None) -> None:
        """Abre o painel de sub-botões de ``group`` ao lado de ``anchor``."""
        from .flyout import Flyout

        if level == 0:
            self._close_flyouts()
            self._flyout_root_id = root_id or group.id
        else:
            # fecha painéis mais profundos que o nível atual
            while len(self._flyouts) > level:
                self._flyouts.pop().destroy()

        fly = Flyout(self, group, anchor, level)
        self._flyouts.append(fly)
        self.register_dialog(fly)

        if not self._flyout_polling:
            self._flyout_polling = True
            self._flyout_miss = 0
            self.after(160, self._flyout_poll)

    def _flyout_child_clicked(self, child: Shortcut, button) -> None:
        """Clique num sub-botão: executa, ou abre sub-painel se for grupo."""
        if child.type == ACTION_GROUP:
            self.open_group(child, button, level=len(self._flyouts))
        else:
            self._close_flyouts()
            self.executor.execute(child)

    def _close_flyouts(self) -> None:
        while self._flyouts:
            fly = self._flyouts.pop()
            try:
                fly.destroy()
            except tk.TclError:
                pass
        self._flyout_root_id = None
        self._flyout_anchor = None
        self._flyout_polling = False
        self._flyout_miss = 0

    def _flyout_poll(self) -> None:
        """Fecha os painéis quando o ponteiro fica fora deles por um tempo."""
        if not self._flyouts:
            self._flyout_polling = False
            return
        if self._pointer_over_flyouts():
            self._flyout_miss = 0
        else:
            self._flyout_miss += 1
            if self._flyout_miss >= 3:  # ~480 ms de tolerância
                self._close_flyouts()
                return
        self.after(160, self._flyout_poll)

    def _pointer_over_flyouts(self) -> bool:
        px, py = self.winfo_pointerx(), self.winfo_pointery()
        widgets = list(self._flyouts)
        if self._flyout_anchor is not None:
            widgets.append(self._flyout_anchor)
        for w in widgets:
            try:
                if not w.winfo_exists():
                    continue
                x, y = w.winfo_rootx(), w.winfo_rooty()
                ww, wh = w.winfo_width(), w.winfo_height()
                if x <= px <= x + ww and y <= py <= y + wh:
                    return True
            except tk.TclError:
                continue
        return False

    def _edit_shortcut(self, shortcut: Optional[Shortcut]) -> None:
        """Abre o editor para um atalho existente ou um novo."""
        from .editor import ShortcutEditor

        def on_save(result: Shortcut) -> None:
            if shortcut is None:
                self.shortcuts.append(result)
            else:
                idx = self._index_of(shortcut.id)
                if idx >= 0:
                    self.shortcuts[idx] = result
            self.set_shortcuts(self.shortcuts)
            self._refresh_settings_window()

        ShortcutEditor(self, shortcut, on_save)

    def _index_of(self, shortcut_id: str) -> int:
        for i, s in enumerate(self.shortcuts):
            if s.id == shortcut_id:
                return i
        return -1

    # ================================================================== #
    # Janelas auxiliares
    # ================================================================== #
    def open_settings(self) -> None:
        from .settings_window import SettingsWindow

        self._close_flyouts()
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.focus_force()
            return
        self._settings_window = SettingsWindow(self)

    def _refresh_settings_window(self) -> None:
        if self._settings_window is not None and self._settings_window.winfo_exists():
            self._settings_window.refresh_list()

    def open_search(self) -> None:
        from .search import SearchOverlay

        self._close_flyouts()
        if self._search_window is not None and self._search_window.winfo_exists():
            self._search_window.focus_force()
            return
        self._search_window = SearchOverlay(self, self.shortcuts, self._run_shortcut)

    def register_dialog(self, window) -> None:
        """Registra um diálogo para suspender a reafirmação de "sempre no topo".

        Enquanto houver diálogos abertos, a barra não força ``-topmost`` — do
        contrário ela ficaria por cima das janelas de configuração/edição.
        """
        self._open_dialogs += 1

        def _on_destroy(event, w=window) -> None:
            if event.widget is w:
                self._open_dialogs = max(0, self._open_dialogs - 1)

        window.bind("<Destroy>", _on_destroy, add="+")

    # ================================================================== #
    # Atalho global
    # ================================================================== #
    def _start_hotkey(self) -> None:
        ok = self.hotkeys.register(self.settings.hotkey)
        if not ok and self.hotkeys.available:
            # falha silenciosa; a tela de config informa o usuário
            pass

    def _restart_hotkey(self) -> None:
        self.hotkeys.register(self.settings.hotkey)

    # ================================================================== #
    # Bandeja do sistema (rodar em segundo plano)
    # ================================================================== #
    def _start_tray(self) -> None:
        """Inicia o ícone da bandeja (falha silenciosa se ``pystray`` faltar)."""
        self.tray.start()

    def _handle_tray_command(self, command: str) -> None:
        """Executa, na thread da UI, um comando vindo do menu da bandeja."""
        if command == "toggle":
            self.toggle_visibility()
        elif command == "search":
            self.show()
            self.open_search()
        elif command == "settings":
            self.show()
            self.open_settings()
        elif command == "quit":
            self.quit_app()

    def toggle_visibility(self) -> None:
        """Mostra/esconde a barra (usado pelo atalho global e pela bandeja)."""
        if self._visible:
            self.hide()
        else:
            self.show()

    def show(self) -> None:
        """Exibe a barra (se estiver escondida)."""
        if self._visible:
            self.attributes("-topmost", self.settings.always_on_top)
            return
        self.deiconify()
        self.attributes("-topmost", self.settings.always_on_top)
        self._visible = True
        self._animate_in()

    def hide(self) -> None:
        """Esconde a barra; o app segue rodando na bandeja do sistema."""
        if not self._visible:
            return
        self._close_flyouts()
        self.withdraw()
        self._visible = False

    # ================================================================== #
    # Loop de manutenção (hotkey + topmost + auto-hide)
    # ================================================================== #
    def _tick(self) -> None:
        # 1) atalho global
        if self.hotkeys.drain() > 0:
            self.toggle_visibility()

        # 1b) comandos vindos da bandeja do sistema
        for command in self.tray.drain():
            self._handle_tray_command(command)
            if command == "quit":
                return  # janela destruída: não reagenda o tick

        # 2) reafirma "sempre no topo" (overrideredirect às vezes perde),
        #    exceto quando há diálogos abertos — senão a barra cobriria-os
        if self._visible and self.settings.always_on_top and self._open_dialogs == 0:
            try:
                self.attributes("-topmost", True)
            except tk.TclError:
                pass

        # 3) esconder automaticamente
        if self._visible:
            self._autohide_tick()

        self.after(_TICK_MS, self._tick)

    def _autohide_tick(self) -> None:
        if (
            not self.settings.auto_hide
            or self.settings.pinned_side == "none"
            or self._dragging
        ):
            if self._hidden_by_autohide:
                self._hidden_by_autohide = False
                self._apply_geometry()
            return

        should_show = self._pointer_in_reveal_zone()
        if should_show and self._hidden_by_autohide:
            self._hidden_by_autohide = False
            self._slide_to(self._shown_xy())
        elif not should_show and not self._hidden_by_autohide:
            self._hidden_by_autohide = True
            self._slide_to(self._hidden_xy())

    def _shown_xy(self):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self._win_w, self._win_h
        side, margin = self.settings.pinned_side, 6
        if side == "left":
            return margin, (sh - h) // 2
        if side == "right":
            return sw - w - margin, (sh - h) // 2
        if side == "top":
            return (sw - w) // 2, margin
        return (sw - w) // 2, sh - h - margin

    def _hidden_xy(self):
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self._win_w, self._win_h
        sliver = 6
        sx, sy = self._shown_xy()
        side = self.settings.pinned_side
        if side == "left":
            return -(w - sliver), sy
        if side == "right":
            return sw - sliver, sy
        if side == "top":
            return sx, -(h - sliver)
        return sx, sh - sliver

    def _pointer_in_reveal_zone(self) -> bool:
        px, py = self.winfo_pointerx(), self.winfo_pointery()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = self._win_w, self._win_h
        sx, sy = self._shown_xy()
        side = self.settings.pinned_side
        edge = 3  # espessura da zona de revelação na borda

        # se o ponteiro está sobre a janela mostrada, mantém visível
        if sx <= px <= sx + w and sy <= py <= sy + h:
            return True
        if side == "left":
            return px <= edge and sy <= py <= sy + h
        if side == "right":
            return px >= sw - edge and sy <= py <= sy + h
        if side == "top":
            return py <= edge and sx <= px <= sx + w
        return py >= sh - edge and sx <= px <= sx + w

    # ================================================================== #
    # Animações
    # ================================================================== #
    def _animate_in(self) -> None:
        """Fade-in suave da opacidade ao abrir/mostrar."""
        target = self.settings.opacity
        steps = 12
        try:
            self.attributes("-alpha", 0.0)
        except tk.TclError:
            return

        def step(i: int) -> None:
            frac = i / steps
            self.attributes("-alpha", target * frac)
            if i < steps:
                self.after(14, lambda: step(i + 1))
            else:
                self.attributes("-alpha", target)

        step(1)

    def _slide_to(self, xy) -> None:
        """Anima a janela até (x, y) — usado no esconder/mostrar automático."""
        if self._anim_job is not None:
            try:
                self.after_cancel(self._anim_job)
            except (ValueError, tk.TclError):
                pass
            self._anim_job = None

        tx, ty = xy
        steps = 10

        def step(i: int) -> None:
            cx, cy = self.winfo_x(), self.winfo_y()
            nx = cx + (tx - cx) * (1 / (steps - i + 1))
            ny = cy + (ty - cy) * (1 / (steps - i + 1))
            self.geometry(f"+{int(round(nx))}+{int(round(ny))}")
            if i < steps:
                self._anim_job = self.after(12, lambda: step(i + 1))
            else:
                self.geometry(f"+{tx}+{ty}")
                self._anim_job = None

        step(1)

    # ================================================================== #
    # Utilidades
    # ================================================================== #
    def _apply_window_attributes(self) -> None:
        try:
            self.attributes("-topmost", self.settings.always_on_top)
            self.attributes("-alpha", self.settings.opacity)
        except tk.TclError:
            pass

    def _hide_from_taskbar(self) -> None:
        """Remove o botão da barra de tarefas (janela do tipo *tool window*).

        Garante que o QuickDock rode em segundo plano sem ocupar espaço na
        barra de tarefas, independentemente de quirks do ``overrideredirect``.
        Falha silenciosamente fora do Windows.
        """
        try:
            import ctypes

            gwl_exstyle = -20
            ws_ex_toolwindow = 0x00000080
            ws_ex_appwindow = 0x00040000

            user32 = ctypes.windll.user32
            hwnd = user32.GetParent(self.winfo_id()) or self.winfo_id()
            style = user32.GetWindowLongW(hwnd, gwl_exstyle)
            style = (style & ~ws_ex_appwindow) | ws_ex_toolwindow
            user32.SetWindowLongW(hwnd, gwl_exstyle, style)
        except Exception:  # noqa: BLE001 - fora do Windows ou sem permissão
            pass

    @staticmethod
    def _ctk_mode(theme: str) -> str:
        return {"dark": "Dark", "light": "Light", "system": "System"}.get(theme, "Dark")

    def _show_error(self, message: str) -> None:
        messagebox.showerror("QuickDock", message)

    # ================================================================== #
    # Encerramento
    # ================================================================== #
    def quit_app(self) -> None:
        self._close_flyouts()
        try:
            if self.settings.pinned_side == "none":
                self._save_position()
            else:
                storage.save_settings(self.settings)
        except Exception:  # noqa: BLE001
            pass
        self.hotkeys.stop()
        self.tray.stop()
        self.destroy()
