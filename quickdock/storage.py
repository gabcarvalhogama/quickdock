"""Camada de persistência (JSON).

Responsável por localizar os arquivos de dados, carregar e salvar as
configurações e os atalhos.

Por padrão, os dados ficam no **perfil do usuário** — em
``%APPDATA%\\QuickDock`` — para que **sobrevivam às atualizações do programa**
(substituir/reinstalar o app não apaga seus atalhos).  O local continua fácil
de editar à mão: basta abrir ``%APPDATA%\\QuickDock`` no Explorer.

Estrutura:

    %APPDATA%\\QuickDock\\settings.json
    %APPDATA%\\QuickDock\\shortcuts.json

**Modo portátil:** se existir um arquivo chamado ``portable.txt`` (ou
``portable``) ao lado do executável, os dados voltam a ficar em
``<pasta_do_app>/data`` — útil para levar tudo num pendrive.

**Migração automática:** se você já tinha dados na pasta ``data`` antiga (ao
lado do app), eles são copiados para o novo local na primeira execução, sem
perda.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import uuid
from pathlib import Path
from typing import List

from .models import (
    ACTION_FOLDER,
    ACTION_MACRO,
    ACTION_MULTI_URL,
    ACTION_URL,
    MacroStep,
    Settings,
    Shortcut,
)

SETTINGS_FILE = "settings.json"
SHORTCUTS_FILE = "shortcuts.json"

#: evita reexecutar a migração a cada chamada de ``data_dir()``.
_migration_done = False


# --------------------------------------------------------------------------- #
# Resolução de caminhos
# --------------------------------------------------------------------------- #
def app_dir() -> Path:
    """Diretório base do aplicativo.

    Funciona tanto rodando via Python quanto empacotado com PyInstaller
    (``sys.frozen``).
    """
    if getattr(sys, "frozen", False):  # executável PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def _is_portable() -> bool:
    """Modo portátil quando há um marcador ``portable``/``portable.txt``."""
    base = app_dir()
    return (base / "portable.txt").exists() or (base / "portable").exists()


def legacy_data_dir() -> Path:
    """Local antigo (ao lado do app), usado para migração e modo portátil."""
    return app_dir() / "data"


def data_dir() -> Path:
    """Pasta de dados efetiva (criada sob demanda).

    - Modo portátil  -> ``<pasta_do_app>/data``.
    - Caso contrário -> ``%APPDATA%/QuickDock`` (fallback ``~/.quickdock``).
    """
    if _is_portable():
        d = legacy_data_dir()
    else:
        base = os.getenv("APPDATA") or os.getenv("XDG_CONFIG_HOME")
        d = (Path(base) / "QuickDock") if base else (Path.home() / ".quickdock")

    d.mkdir(parents=True, exist_ok=True)
    _migrate_legacy(d)
    return d


def _migrate_legacy(target: Path) -> None:
    """Copia os JSON da pasta antiga para o novo local, uma única vez.

    Só age se o destino ainda não tiver o arquivo correspondente — nunca
    sobrescreve dados existentes.
    """
    global _migration_done
    if _migration_done:
        return
    _migration_done = True

    legacy = legacy_data_dir()
    if legacy.resolve() == target.resolve():
        return  # modo portátil: origem e destino coincidem
    for name in (SETTINGS_FILE, SHORTCUTS_FILE):
        src, dst = legacy / name, target / name
        if src.exists() and not dst.exists():
            try:
                shutil.copy2(src, dst)
            except OSError:
                pass


# --------------------------------------------------------------------------- #
# Leitura/escrita genérica
# --------------------------------------------------------------------------- #
def _read_json(path: Path):
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, data) -> None:
    """Escrita atômica: grava em arquivo temporário e substitui."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    tmp.replace(path)


# --------------------------------------------------------------------------- #
# Configurações
# --------------------------------------------------------------------------- #
def load_settings() -> Settings:
    path = data_dir() / SETTINGS_FILE
    if not path.exists():
        settings = Settings()
        save_settings(settings)
        return settings
    try:
        return Settings.from_dict(_read_json(path))
    except (json.JSONDecodeError, OSError, ValueError):
        # arquivo corrompido -> volta ao padrão sem quebrar o app
        return Settings()


def save_settings(settings: Settings) -> None:
    _write_json(data_dir() / SETTINGS_FILE, settings.to_dict())


# --------------------------------------------------------------------------- #
# Atalhos
# --------------------------------------------------------------------------- #
def load_shortcuts() -> List[Shortcut]:
    path = data_dir() / SHORTCUTS_FILE
    if not path.exists():
        shortcuts = _default_shortcuts()
        save_shortcuts(shortcuts)
        return shortcuts
    try:
        raw = _read_json(path)
        return [Shortcut.from_dict(item) for item in raw]
    except (json.JSONDecodeError, OSError, ValueError):
        return _default_shortcuts()


def save_shortcuts(shortcuts: List[Shortcut]) -> None:
    data = [s.to_dict() for s in shortcuts]
    _write_json(data_dir() / SHORTCUTS_FILE, data)


# --------------------------------------------------------------------------- #
# Atalhos de exemplo (primeira execução)
# --------------------------------------------------------------------------- #
def _default_shortcuts() -> List[Shortcut]:
    """Conjunto inicial de exemplos, útil já na primeira abertura."""
    return [
        Shortcut(
            id=uuid.uuid4().hex,
            name="Claude",
            type=ACTION_URL,
            target="https://claude.ai",
            tooltip="Abrir Claude",
        ),
        Shortcut(
            id=uuid.uuid4().hex,
            name="Jurídico Pro",
            type=ACTION_MULTI_URL,
            targets=[
                "https://app.juridicopro.com.br",
                "https://chatgpt.com",
            ],
            tooltip="Abrir Jurídico Pro + ChatGPT",
        ),
        Shortcut(
            id=uuid.uuid4().hex,
            name="Meus arquivos",
            type=ACTION_FOLDER,
            target="%USERPROFILE%",
            tooltip="Abrir a pasta do usuário",
        ),
        Shortcut(
            id=uuid.uuid4().hex,
            name="Produção",
            type=ACTION_MACRO,
            tooltip="Rotina de produção",
            steps=[
                MacroStep(type=ACTION_FOLDER, target="%USERPROFILE%\\Desktop", wait=1.0),
                MacroStep(type=ACTION_URL, target="https://claude.ai", wait=1.0),
                MacroStep(type=ACTION_URL, target="https://chatgpt.com", wait=0.0),
            ],
        ),
    ]
