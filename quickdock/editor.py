"""Diálogos de adicionar/editar atalho e passos de macro.

- :class:`ShortcutEditor` — formulário completo de um atalho, com campos que
  mudam conforme o tipo de ação escolhido.
- :class:`MacroStepEditor` — formulário de um passo individual de macro.

Ambos são janelas ``CTkToplevel`` modais.  Ao confirmar, chamam o callback
``on_save`` com o objeto resultante; a persistência é feita por quem chamou.
"""

from __future__ import annotations

from tkinter import filedialog, messagebox
from typing import Callable, List, Optional

import customtkinter as ctk

from . import icons
from .models import (
    ACTION_CHROME,
    ACTION_COMMAND,
    ACTION_FILE,
    ACTION_FOLDER,
    ACTION_GROUP,
    ACTION_LABELS,
    ACTION_MACRO,
    ACTION_MULTI_URL,
    ACTION_PROGRAM,
    ACTION_SCRIPT,
    ACTION_URL,
    ALL_ACTION_TYPES,
    STEP_ACTION_TYPES,
    MacroStep,
    Shortcut,
)

# rótulo -> chave e chave -> rótulo
_LABEL_TO_TYPE = {ACTION_LABELS[t]: t for t in ALL_ACTION_TYPES}
_STEP_LABEL_TO_TYPE = {ACTION_LABELS[t]: t for t in STEP_ACTION_TYPES}


class _BaseDialog(ctk.CTkToplevel):
    """Base com utilidades comuns aos diálogos (posicionamento, topo, modal)."""

    def __init__(self, master, dock, title: str, width: int, height: int) -> None:
        super().__init__(master)
        self._dock = dock
        self.title(title)
        self.geometry(f"{width}x{height}")
        self.minsize(width, height)
        self.configure(fg_color=("#f3f4f6", "#1a1b1e"))

        # acima da barra (que é always-on-top) e com foco
        self.attributes("-topmost", True)
        self.after(10, self._center)
        self.after(30, self.focus_force)
        if dock is not None:
            dock.register_dialog(self)

    def _center(self) -> None:
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        x = (self.winfo_screenwidth() - w) // 2
        y = (self.winfo_screenheight() - h) // 3
        self.geometry(f"+{x}+{y}")


class ShortcutEditor(_BaseDialog):
    """Editor de um atalho (novo ou existente)."""

    def __init__(
        self,
        master,
        dock,
        shortcut: Optional[Shortcut],
        on_save: Callable[[Shortcut], None],
    ) -> None:
        super().__init__(master, dock, "Editar atalho", 560, 640)
        self._on_save = on_save
        self._original = shortcut
        # cópia de trabalho (não altera o original até salvar)
        self._model = Shortcut.from_dict(shortcut.to_dict()) if shortcut else Shortcut()
        self._macro_steps: List[MacroStep] = list(self._model.steps)
        self._children: List[Shortcut] = list(self._model.children)
        self._fields: dict = {}

        self._build()

    # ------------------------------------------------------------------ #
    def _build(self) -> None:
        body = ctk.CTkScrollableFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=(14, 6))

        # Nome
        self._fields["name"] = self._labeled_entry(body, "Nome", self._model.name)

        # Tipo
        ctk.CTkLabel(body, text="Ação", anchor="w").pack(fill="x", pady=(10, 2))
        self._type_menu = ctk.CTkOptionMenu(
            body,
            values=[ACTION_LABELS[t] for t in ALL_ACTION_TYPES],
            command=self._on_type_change,
        )
        self._type_menu.set(ACTION_LABELS[self._model.type])
        self._type_menu.pack(fill="x")

        # Área dinâmica (muda conforme o tipo)
        self._dyn = ctk.CTkFrame(body, fg_color="transparent")
        self._dyn.pack(fill="both", expand=True, pady=(6, 0))

        # Ícone + tooltip (comuns a todos)
        self._common = ctk.CTkFrame(body, fg_color="transparent")
        self._common.pack(fill="x", pady=(6, 0))
        self._build_common(self._common)

        self._render_fields()

        # Rodapé
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(4, 14))
        ctk.CTkButton(footer, text="Cancelar", width=110, fg_color="gray40",
                      hover_color="gray30", command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="Salvar", width=140,
                      command=self._save).pack(side="right")

    # ------------------------------------------------------------------ #
    # Campos comuns (ícone e tooltip)
    # ------------------------------------------------------------------ #
    def _build_common(self, master) -> None:
        row = ctk.CTkFrame(master, fg_color="transparent")
        row.pack(fill="x", pady=(10, 2))
        ctk.CTkLabel(row, text="Ícone — imagem, emoji ou a letra do nome",
                     anchor="w").pack(side="left")

        self._icon_preview = ctk.CTkLabel(row, text="", width=34)
        self._icon_preview.pack(side="right")

        entry_row = ctk.CTkFrame(master, fg_color="transparent")
        entry_row.pack(fill="x")
        self._fields["icon"] = ctk.CTkEntry(entry_row)
        self._fields["icon"].insert(0, self._model.icon)
        self._fields["icon"].pack(side="left", fill="x", expand=True)
        self._fields["icon"].bind("<KeyRelease>", lambda _e: self._update_icon_preview())
        # escolher emoji
        ctk.CTkButton(entry_row, text=" Emoji",
                      image=icons.get_emoji_image("😀", 18), compound="left",
                      width=92, command=self._open_emoji_picker).pack(side="left", padx=(6, 0))
        # procurar imagem
        ctk.CTkButton(entry_row, text="…", width=40,
                      command=self._browse_icon).pack(side="left", padx=(6, 0))
        # limpar (volta para a letra automática)
        ctk.CTkButton(entry_row, text="✕", width=36, fg_color="gray40",
                      hover_color="gray30", command=self._clear_icon).pack(side="left", padx=(6, 0))

        self._fields["tooltip"] = self._labeled_entry(master, "Dica (tooltip)", self._model.tooltip)
        self._update_icon_preview()

    def _open_emoji_picker(self) -> None:
        from .emoji_picker import EmojiPicker

        EmojiPicker(self, self._dock, self._set_emoji)

    def _set_emoji(self, char: str) -> None:
        self._fields["icon"].delete(0, "end")
        self._fields["icon"].insert(0, icons.EMOJI_PREFIX + char)
        self._update_icon_preview()

    def _clear_icon(self) -> None:
        self._fields["icon"].delete(0, "end")
        self._update_icon_preview()

    def _update_icon_preview(self) -> None:
        temp = Shortcut(
            name=self._fields["name"].get() or "?",
            type=self._current_type(),
            target=self._first_target_value(),
            icon=self._fields["icon"].get().strip(),
        )
        img = icons.get_icon(temp, 28)
        self._icon_preview.configure(image=img)

    def _first_target_value(self) -> str:
        if "target" in self._fields:
            widget = self._fields["target"]
            if isinstance(widget, ctk.CTkTextbox):
                return widget.get("1.0", "end").strip().splitlines()[0] if widget.get("1.0", "end").strip() else ""
            return widget.get()
        return self._model.target

    # ------------------------------------------------------------------ #
    # Campos dinâmicos por tipo
    # ------------------------------------------------------------------ #
    def _on_type_change(self, _label: str) -> None:
        self._render_fields()
        self._update_icon_preview()

    def _current_type(self) -> str:
        return _LABEL_TO_TYPE.get(self._type_menu.get(), ACTION_URL)

    def _render_fields(self) -> None:
        for child in self._dyn.winfo_children():
            child.destroy()
        # remove refs antigas dos campos dinâmicos
        for key in ("target", "targets", "args", "cwd", "minimized",
                    "chrome_menu", "chrome_entry"):
            self._fields.pop(key, None)

        t = self._current_type()

        if t == ACTION_URL:
            self._fields["target"] = self._labeled_entry(self._dyn, "URL", self._model.target)

        elif t == ACTION_MULTI_URL:
            ctk.CTkLabel(self._dyn, text="URLs (uma por linha)", anchor="w").pack(fill="x", pady=(8, 2))
            box = ctk.CTkTextbox(self._dyn, height=120)
            box.pack(fill="x")
            box.insert("1.0", "\n".join(self._model.targets))
            self._fields["targets"] = box

        elif t == ACTION_CHROME:
            ctk.CTkLabel(self._dyn, text="URLs (uma por linha)", anchor="w").pack(fill="x", pady=(8, 2))
            box = ctk.CTkTextbox(self._dyn, height=100)
            box.pack(fill="x")
            box.insert("1.0", "\n".join(self._model.targets) or self._model.target)
            self._fields["targets"] = box
            self._build_chrome_profile_field(self._dyn)

        elif t in (ACTION_PROGRAM, ACTION_FILE, ACTION_SCRIPT):
            self._fields["target"] = self._path_field(
                self._dyn, "Caminho", self._model.target, kind="file"
            )
            self._fields["args"] = self._labeled_entry(self._dyn, "Argumentos", self._model.args)
            self._fields["cwd"] = self._path_field(
                self._dyn, "Pasta inicial (Working Directory)",
                self._model.working_directory, kind="folder"
            )
            self._add_minimized(self._dyn)

        elif t == ACTION_FOLDER:
            self._fields["target"] = self._path_field(
                self._dyn, "Pasta", self._model.target, kind="folder"
            )

        elif t == ACTION_COMMAND:
            self._fields["target"] = self._labeled_entry(self._dyn, "Comando", self._model.target)
            self._fields["args"] = self._labeled_entry(self._dyn, "Argumentos", self._model.args)
            self._fields["cwd"] = self._path_field(
                self._dyn, "Pasta inicial (Working Directory)",
                self._model.working_directory, kind="folder"
            )
            self._add_minimized(self._dyn)

        elif t == ACTION_MACRO:
            self._build_macro_editor(self._dyn)

        elif t == ACTION_GROUP:
            self._build_group_editor(self._dyn)

    def _add_minimized(self, master) -> None:
        sw = ctk.CTkSwitch(master, text="Abrir minimizado")
        sw.pack(anchor="w", pady=(10, 2))
        if self._model.minimized:
            sw.select()
        self._fields["minimized"] = sw

    def _build_chrome_profile_field(self, master) -> None:
        """Seletor de perfil do Chrome (menu com nomes amigáveis)."""
        from .browsers import chrome_profiles

        ctk.CTkLabel(master, text="Perfil do Chrome", anchor="w").pack(fill="x", pady=(10, 2))
        profiles = chrome_profiles()
        current = self._model.browser_profile or "Default"

        if profiles:
            self._chrome_map = {}
            values = []
            for folder, name in profiles:
                label = f"{name}   ({folder})"
                values.append(label)
                self._chrome_map[label] = folder
            menu = ctk.CTkOptionMenu(master, values=values)
            selected = next((lbl for lbl, folder in self._chrome_map.items()
                             if folder == current), values[0])
            menu.set(selected)
            menu.pack(fill="x")
            self._fields["chrome_menu"] = menu
        else:
            ctk.CTkLabel(
                master, text="(perfis não detectados — informe a pasta, ex.: Default, Profile 1)",
                anchor="w", text_color="gray").pack(fill="x")
            entry = ctk.CTkEntry(master)
            entry.insert(0, current)
            entry.pack(fill="x")
            self._fields["chrome_entry"] = entry

    # ------------------------------------------------------------------ #
    # Editor de macro embutido
    # ------------------------------------------------------------------ #
    def _build_macro_editor(self, master) -> None:
        header = ctk.CTkFrame(master, fg_color="transparent")
        header.pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(header, text="Passos da macro", anchor="w").pack(side="left")
        ctk.CTkButton(header, text="＋ Passo", width=90,
                      command=self._add_macro_step).pack(side="right")

        self._steps_frame = ctk.CTkScrollableFrame(master, height=200, fg_color=("#e9eaee", "#232427"))
        self._steps_frame.pack(fill="both", expand=True)
        self._render_macro_steps()

    def _render_macro_steps(self) -> None:
        for child in self._steps_frame.winfo_children():
            child.destroy()

        if not self._macro_steps:
            ctk.CTkLabel(self._steps_frame, text="Nenhum passo. Clique em “＋ Passo”.",
                         text_color="gray").pack(pady=16)
            return

        for i, step in enumerate(self._macro_steps):
            row = ctk.CTkFrame(self._steps_frame, fg_color=("#f3f4f6", "#2b2c30"), corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)
            ctk.CTkLabel(row, text=f"{i + 1}.", width=24).pack(side="left", padx=(6, 0))
            ctk.CTkLabel(row, text=step.describe(), anchor="w").pack(
                side="left", fill="x", expand=True, padx=4)
            ctk.CTkButton(row, text="✕", width=28, fg_color="transparent",
                          hover_color="#c0392b",
                          command=lambda idx=i: self._remove_macro_step(idx)).pack(side="right", padx=(0, 4))
            ctk.CTkButton(row, text="✎", width=28, fg_color="transparent",
                          hover_color="gray40",
                          command=lambda idx=i: self._edit_macro_step(idx)).pack(side="right")
            ctk.CTkButton(row, text="▼", width=24, fg_color="transparent", hover_color="gray40",
                          command=lambda idx=i: self._move_macro_step(idx, 1)).pack(side="right")
            ctk.CTkButton(row, text="▲", width=24, fg_color="transparent", hover_color="gray40",
                          command=lambda idx=i: self._move_macro_step(idx, -1)).pack(side="right")

    def _add_macro_step(self) -> None:
        MacroStepEditor(self, self._dock, None, self._on_step_saved)

    def _edit_macro_step(self, index: int) -> None:
        MacroStepEditor(self, self._dock, self._macro_steps[index],
                        lambda s, i=index: self._on_step_saved(s, i))

    def _on_step_saved(self, step: MacroStep, index: Optional[int] = None) -> None:
        if index is None:
            self._macro_steps.append(step)
        else:
            self._macro_steps[index] = step
        self._render_macro_steps()

    def _remove_macro_step(self, index: int) -> None:
        del self._macro_steps[index]
        self._render_macro_steps()

    def _move_macro_step(self, index: int, delta: int) -> None:
        j = index + delta
        if 0 <= j < len(self._macro_steps):
            self._macro_steps[index], self._macro_steps[j] = (
                self._macro_steps[j], self._macro_steps[index])
            self._render_macro_steps()

    # ------------------------------------------------------------------ #
    # Editor de grupo (sub-botões) — reaproveita o próprio ShortcutEditor
    # para cada filho, permitindo aninhamento.
    # ------------------------------------------------------------------ #
    def _build_group_editor(self, master) -> None:
        header = ctk.CTkFrame(master, fg_color="transparent")
        header.pack(fill="x", pady=(8, 2))
        ctk.CTkLabel(header, text="Sub-botões", anchor="w").pack(side="left")
        ctk.CTkButton(header, text="＋ Sub-botão", width=120,
                      command=self._add_child).pack(side="right")

        self._children_frame = ctk.CTkScrollableFrame(
            master, height=200, fg_color=("#e9eaee", "#232427"))
        self._children_frame.pack(fill="both", expand=True)
        self._render_children()

    def _render_children(self) -> None:
        for child in self._children_frame.winfo_children():
            child.destroy()

        if not self._children:
            ctk.CTkLabel(self._children_frame,
                         text="Nenhum sub-botão. Clique em “＋ Sub-botão”.",
                         text_color="gray").pack(pady=16)
            return

        for i, sc in enumerate(self._children):
            row = ctk.CTkFrame(self._children_frame,
                               fg_color=("#f3f4f6", "#2b2c30"), corner_radius=6)
            row.pack(fill="x", pady=3, padx=2)
            ctk.CTkLabel(row, image=icons.get_icon(sc, 22), text="",
                         width=26).pack(side="left", padx=(6, 2))
            label = sc.name
            if sc.type == ACTION_GROUP:
                label += f"  ▸ ({len(sc.children)})"
            ctk.CTkLabel(row, text=label, anchor="w").pack(
                side="left", fill="x", expand=True, padx=4)
            ctk.CTkButton(row, text="✕", width=28, fg_color="transparent",
                          hover_color="#c0392b",
                          command=lambda idx=i: self._remove_child(idx)).pack(side="right", padx=(0, 4))
            ctk.CTkButton(row, text="✎", width=28, fg_color="transparent",
                          hover_color="gray40",
                          command=lambda idx=i: self._edit_child(idx)).pack(side="right")
            ctk.CTkButton(row, text="▼", width=24, fg_color="transparent", hover_color="gray40",
                          command=lambda idx=i: self._move_child(idx, 1)).pack(side="right")
            ctk.CTkButton(row, text="▲", width=24, fg_color="transparent", hover_color="gray40",
                          command=lambda idx=i: self._move_child(idx, -1)).pack(side="right")

    def _add_child(self) -> None:
        ShortcutEditor(self, self._dock, None, self._on_child_saved)

    def _edit_child(self, index: int) -> None:
        ShortcutEditor(self, self._dock, self._children[index],
                       lambda sc, i=index: self._on_child_saved(sc, i))

    def _on_child_saved(self, sc: Shortcut, index: Optional[int] = None) -> None:
        if index is None:
            self._children.append(sc)
        else:
            self._children[index] = sc
        self._render_children()

    def _remove_child(self, index: int) -> None:
        del self._children[index]
        self._render_children()

    def _move_child(self, index: int, delta: int) -> None:
        j = index + delta
        if 0 <= j < len(self._children):
            self._children[index], self._children[j] = (
                self._children[j], self._children[index])
            self._render_children()

    # ------------------------------------------------------------------ #
    # Widgets utilitários
    # ------------------------------------------------------------------ #
    def _labeled_entry(self, master, label: str, value: str) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=label, anchor="w").pack(fill="x", pady=(8, 2))
        entry = ctk.CTkEntry(master)
        entry.insert(0, value or "")
        entry.pack(fill="x")
        return entry

    def _path_field(self, master, label: str, value: str, kind: str) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=label, anchor="w").pack(fill="x", pady=(8, 2))
        row = ctk.CTkFrame(master, fg_color="transparent")
        row.pack(fill="x")
        entry = ctk.CTkEntry(row)
        entry.insert(0, value or "")
        entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row, text="…", width=40,
            command=lambda: self._browse_path(entry, kind),
        ).pack(side="left", padx=(6, 0))
        return entry

    def _browse_path(self, entry: ctk.CTkEntry, kind: str) -> None:
        if kind == "folder":
            path = filedialog.askdirectory(parent=self)
        else:
            path = filedialog.askopenfilename(parent=self)
        if path:
            entry.delete(0, "end")
            entry.insert(0, path)
            self._update_icon_preview()

    def _browse_icon(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Escolher ícone",
            filetypes=[("Imagens", "*.png *.ico *.jpg *.jpeg *.bmp *.gif"), ("Todos", "*.*")],
        )
        if path:
            self._fields["icon"].delete(0, "end")
            self._fields["icon"].insert(0, path)
            self._update_icon_preview()

    # ------------------------------------------------------------------ #
    # Salvar
    # ------------------------------------------------------------------ #
    def _save(self) -> None:
        name = self._fields["name"].get().strip()
        if not name:
            messagebox.showwarning("QuickDock", "Informe um nome para o atalho.", parent=self)
            return

        t = self._current_type()
        self._model.name = name
        self._model.type = t
        self._model.icon = self._fields["icon"].get().strip()
        self._model.tooltip = self._fields["tooltip"].get().strip()

        # zera campos e preenche conforme o tipo
        self._model.target = ""
        self._model.targets = []
        self._model.args = ""
        self._model.working_directory = ""
        self._model.minimized = False
        self._model.browser_profile = ""
        self._model.steps = []
        self._model.children = []

        if t == ACTION_MULTI_URL:
            box = self._fields["targets"]
            self._model.targets = [
                ln.strip() for ln in box.get("1.0", "end").splitlines() if ln.strip()
            ]
        elif t == ACTION_CHROME:
            box = self._fields["targets"]
            self._model.targets = [
                ln.strip() for ln in box.get("1.0", "end").splitlines() if ln.strip()
            ]
            if "chrome_menu" in self._fields:
                self._model.browser_profile = self._chrome_map.get(
                    self._fields["chrome_menu"].get(), "Default")
            elif "chrome_entry" in self._fields:
                self._model.browser_profile = self._fields["chrome_entry"].get().strip() or "Default"
        elif t == ACTION_MACRO:
            self._model.steps = list(self._macro_steps)
        elif t == ACTION_GROUP:
            self._model.children = list(self._children)
        else:
            if "target" in self._fields:
                self._model.target = self._fields["target"].get().strip()
            if "args" in self._fields:
                self._model.args = self._fields["args"].get().strip()
            if "cwd" in self._fields:
                self._model.working_directory = self._fields["cwd"].get().strip()
            if "minimized" in self._fields:
                self._model.minimized = bool(self._fields["minimized"].get())

        self._on_save(self._model)
        self.destroy()


# --------------------------------------------------------------------------- #
# Editor de passo de macro
# --------------------------------------------------------------------------- #
class MacroStepEditor(_BaseDialog):
    """Formulário de um passo de macro."""

    def __init__(
        self,
        master,
        dock,
        step: Optional[MacroStep],
        on_save: Callable[[MacroStep], None],
    ) -> None:
        super().__init__(master, dock, "Passo da macro", 480, 470)
        self._on_save = on_save
        self._step = MacroStep.from_dict(step.to_dict()) if step else MacroStep(type=ACTION_URL)
        self._build()

    def _build(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=16, pady=14)

        ctk.CTkLabel(body, text="Ação", anchor="w").pack(fill="x", pady=(0, 2))
        self._type_menu = ctk.CTkOptionMenu(
            body,
            values=[ACTION_LABELS[t] for t in STEP_ACTION_TYPES],
            command=lambda _l: self._update_hint(),
        )
        self._type_menu.set(ACTION_LABELS.get(self._step.type, ACTION_LABELS[ACTION_URL]))
        self._type_menu.pack(fill="x")

        self._hint = ctk.CTkLabel(body, text="", anchor="w", text_color="gray")
        self._hint.pack(fill="x", pady=(6, 2))
        self._target = ctk.CTkTextbox(body, height=90)
        pre = "\n".join(self._step.targets) if self._step.targets else self._step.target
        self._target.insert("1.0", pre)
        self._target.pack(fill="x")

        self._args = self._entry(body, "Argumentos", self._step.args)
        self._cwd = self._entry(body, "Pasta inicial", self._step.working_directory)
        self._profile = self._entry(
            body, "Perfil do Chrome (só p/ 'Abrir URL no Chrome')", self._step.browser_profile)

        self._minimized = ctk.CTkSwitch(body, text="Abrir minimizado")
        self._minimized.pack(anchor="w", pady=(10, 4))
        if self._step.minimized:
            self._minimized.select()

        self._wait = self._entry(body, "Esperar após o passo (segundos)", f"{self._step.wait:g}")

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=16, pady=(0, 14))
        ctk.CTkButton(footer, text="Cancelar", width=100, fg_color="gray40",
                      hover_color="gray30", command=self.destroy).pack(side="right", padx=(8, 0))
        ctk.CTkButton(footer, text="OK", width=120, command=self._save).pack(side="right")

        self._update_hint()

    def _entry(self, master, label, value) -> ctk.CTkEntry:
        ctk.CTkLabel(master, text=label, anchor="w").pack(fill="x", pady=(8, 2))
        e = ctk.CTkEntry(master)
        e.insert(0, value or "")
        e.pack(fill="x")
        return e

    def _current_type(self) -> str:
        return _STEP_LABEL_TO_TYPE.get(self._type_menu.get(), ACTION_URL)

    def _update_hint(self) -> None:
        t = self._current_type()
        if t == ACTION_MULTI_URL:
            self._hint.configure(text="Alvo — uma URL por linha")
        elif t == ACTION_CHROME:
            self._hint.configure(text="Alvo — uma URL por linha (abre no Chrome)")
        elif t == ACTION_COMMAND:
            self._hint.configure(text="Alvo — comando do Windows")
        else:
            self._hint.configure(text="Alvo — caminho, URL ou comando")

    def _save(self) -> None:
        t = self._current_type()
        lines = [ln.strip() for ln in self._target.get("1.0", "end").splitlines() if ln.strip()]

        self._step.type = t
        self._step.args = self._args.get().strip()
        self._step.working_directory = self._cwd.get().strip()
        self._step.minimized = bool(self._minimized.get())
        self._step.browser_profile = self._profile.get().strip()
        try:
            self._step.wait = float((self._wait.get() or "0").replace(",", "."))
        except ValueError:
            self._step.wait = 0.0

        if t in (ACTION_MULTI_URL, ACTION_CHROME):
            self._step.targets = lines
            self._step.target = ""
        else:
            self._step.target = lines[0] if lines else ""
            self._step.targets = []

        self._on_save(self._step)
        self.destroy()
