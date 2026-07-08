"""Modelos de dados da aplicação.

Contém as estruturas usadas em todo o QuickDock.  Todas são ``dataclasses``
simples, com métodos auxiliares de (de)serialização para dicionários — de
forma que o formato JSON de persistência fique isolado do restante do código.

Tipos de ação suportados (``ActionType``):

- ``url``       : abre uma única URL.
- ``multi_url`` : abre várias URLs de uma vez.
- ``program``   : executa um programa (.exe) com argumentos opcionais.
- ``folder``    : abre uma pasta no Explorer.
- ``file``      : abre um arquivo com o aplicativo padrão.
- ``command``   : executa um comando do Windows (shell).
- ``script``    : executa um script (.bat, .ps1, .py).
- ``macro``     : executa uma sequência de passos com esperas entre eles.
- ``group``     : agrupa sub-botões; ao clicar, abre um painel com os filhos
                  (que podem ser de qualquer tipo, inclusive outros grupos).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List


# --------------------------------------------------------------------------- #
# Tipos de ação
# --------------------------------------------------------------------------- #
ACTION_URL = "url"
ACTION_MULTI_URL = "multi_url"
ACTION_PROGRAM = "program"
ACTION_FOLDER = "folder"
ACTION_FILE = "file"
ACTION_COMMAND = "command"
ACTION_SCRIPT = "script"
ACTION_MACRO = "macro"
ACTION_GROUP = "group"
ACTION_CHROME = "chrome"

#: Ordem e rótulos amigáveis (usados nos menus da interface).
ACTION_LABELS: Dict[str, str] = {
    ACTION_URL: "Abrir URL",
    ACTION_MULTI_URL: "Abrir várias URLs",
    ACTION_CHROME: "Abrir URL no Chrome (perfil)",
    ACTION_PROGRAM: "Abrir programa (.exe)",
    ACTION_FOLDER: "Abrir pasta",
    ACTION_FILE: "Abrir arquivo",
    ACTION_COMMAND: "Executar comando",
    ACTION_SCRIPT: "Executar script (.bat/.ps1/.py)",
    ACTION_MACRO: "Macro (sequência de passos)",
    ACTION_GROUP: "Grupo (sub-botões)",
}

#: Tipos que podem aparecer como passo de uma macro (macro não aninha macro).
STEP_ACTION_TYPES: List[str] = [
    ACTION_URL,
    ACTION_MULTI_URL,
    ACTION_CHROME,
    ACTION_PROGRAM,
    ACTION_FOLDER,
    ACTION_FILE,
    ACTION_COMMAND,
    ACTION_SCRIPT,
]

#: Todos os tipos usáveis num atalho/sub-botão (grupo pode conter grupo).
ALL_ACTION_TYPES: List[str] = STEP_ACTION_TYPES + [ACTION_MACRO, ACTION_GROUP]


# --------------------------------------------------------------------------- #
# Passo de macro
# --------------------------------------------------------------------------- #
@dataclass
class MacroStep:
    """Um passo individual dentro de uma macro."""

    type: str = ACTION_PROGRAM
    target: str = ""
    targets: List[str] = field(default_factory=list)
    args: str = ""
    working_directory: str = ""
    minimized: bool = False
    browser_profile: str = ""  # perfil do Chrome (tipo ``chrome``)
    wait: float = 0.0  # segundos de espera *após* executar o passo

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MacroStep":
        return cls(
            type=data.get("type", ACTION_PROGRAM),
            target=data.get("target", ""),
            targets=list(data.get("targets", []) or []),
            args=data.get("args", ""),
            working_directory=data.get("working_directory", ""),
            minimized=bool(data.get("minimized", False)),
            browser_profile=data.get("browser_profile", ""),
            wait=float(data.get("wait", 0.0) or 0.0),
        )

    def describe(self) -> str:
        """Descrição curta e legível do passo (para listas na interface)."""
        label = ACTION_LABELS.get(self.type, self.type)
        alvo = self.target or ", ".join(self.targets)
        texto = f"{label}: {alvo}" if alvo else label
        if self.wait:
            texto += f"  (esperar {self.wait:g}s)"
        return texto


# --------------------------------------------------------------------------- #
# Atalho (botão do dock)
# --------------------------------------------------------------------------- #
@dataclass
class Shortcut:
    """Definição de um atalho exibido como botão na barra."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    name: str = "Novo atalho"
    type: str = ACTION_URL
    target: str = ""
    targets: List[str] = field(default_factory=list)  # usado por ``multi_url``
    args: str = ""
    working_directory: str = ""
    icon: str = ""                                     # caminho de imagem opcional
    tooltip: str = ""
    minimized: bool = False
    browser_profile: str = ""                          # perfil do Chrome (tipo ``chrome``)
    steps: List[MacroStep] = field(default_factory=list)      # usado por ``macro``
    children: List["Shortcut"] = field(default_factory=list)  # usado por ``group``

    # --- serialização ----------------------------------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["steps"] = [s.to_dict() for s in self.steps]
        data["children"] = [c.to_dict() for c in self.children]  # recursivo
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Shortcut":
        return cls(
            id=data.get("id") or uuid.uuid4().hex,
            name=data.get("name", "Atalho"),
            type=data.get("type", ACTION_URL),
            target=data.get("target", ""),
            targets=list(data.get("targets", []) or []),
            args=data.get("args", ""),
            working_directory=data.get("working_directory", ""),
            icon=data.get("icon", ""),
            tooltip=data.get("tooltip", ""),
            minimized=bool(data.get("minimized", False)),
            browser_profile=data.get("browser_profile", ""),
            steps=[MacroStep.from_dict(s) for s in data.get("steps", []) or []],
            children=[cls.from_dict(c) for c in data.get("children", []) or []],
        )

    # --- utilidades ------------------------------------------------------- #
    @property
    def tooltip_text(self) -> str:
        """Texto da dica; cai para o nome quando não há tooltip explícito."""
        return self.tooltip.strip() or self.name


# --------------------------------------------------------------------------- #
# Configurações globais
# --------------------------------------------------------------------------- #
@dataclass
class Settings:
    """Preferências globais da aplicação."""

    orientation: str = "vertical"      # "vertical" | "horizontal"
    theme: str = "dark"                # "dark" | "light" | "system"
    opacity: float = 0.96              # 0.30 .. 1.00
    pos_x: int | None = None           # posição salva (None = centralizar)
    pos_y: int | None = None
    locked: bool = False               # bloquear posição (não arrastar)
    auto_hide: bool = False            # esconder automaticamente na borda
    pinned_side: str = "none"          # "none"|"left"|"right"|"top"|"bottom"
    hotkey: str = "ctrl+space"         # atalho global para mostrar/esconder
    button_size: int = 46              # tamanho do botão (px)
    label_position: str = "none"       # rótulo: "none" | "side" | "below"
    corner_radius: int = 18            # raio das bordas arredondadas
    always_on_top: bool = True         # manter sempre acima
    start_hidden: bool = False         # iniciar escondido (só na bandeja)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        base = cls()
        for key in base.__dict__:
            if key in data and data[key] is not None:
                setattr(base, key, data[key])
        # migração: versões antigas usavam ``show_labels`` (bool)
        if "label_position" not in data and data.get("show_labels"):
            base.label_position = "side"
        # normalizações defensivas
        base.opacity = max(0.30, min(1.0, float(base.opacity)))
        base.button_size = int(max(32, min(72, base.button_size)))
        base.corner_radius = int(max(0, min(40, base.corner_radius)))
        if base.orientation not in ("vertical", "horizontal"):
            base.orientation = "vertical"
        if base.label_position not in ("none", "side", "below"):
            base.label_position = "none"
        return base
