"""Inicialização automática com o Windows (chave *Run* do registro).

Usa apenas a biblioteca padrão (``winreg``).  Registra o QuickDock em
``HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run`` — o
que **não exige privilégios de administrador** e afeta somente o usuário atual.

Funciona tanto rodando via Python (usa ``pythonw.exe`` para não abrir console)
quanto empacotado com PyInstaller (usa o próprio ``.exe``).  Em plataformas
não-Windows, todas as funções degradam para *no-ops* seguros.
"""

from __future__ import annotations

import sys
from pathlib import Path

_APP_NAME = "QuickDock"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

try:  # disponível apenas no Windows
    import winreg  # type: ignore

    _AVAILABLE = True
except Exception:  # noqa: BLE001
    winreg = None  # type: ignore
    _AVAILABLE = False


def available() -> bool:
    """Indica se o registro do Windows está acessível (plataforma Windows)."""
    return _AVAILABLE


def _launch_command() -> str:
    """Comando a ser executado no login do usuário."""
    if getattr(sys, "frozen", False):  # executável PyInstaller
        return f'"{Path(sys.executable).resolve()}"'
    # rodando via Python: prefere pythonw.exe (sem janela de console)
    script = Path(sys.argv[0]).resolve()
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    interpreter = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{interpreter}" "{script}"'


def is_enabled() -> bool:
    """Indica se o QuickDock está registrado para iniciar com o Windows."""
    if not _AVAILABLE:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except OSError:  # inclui FileNotFoundError (valor ausente)
        return False


def set_enabled(enabled: bool) -> bool:
    """Ativa/desativa o início automático.  Retorna ``True`` em caso de sucesso."""
    if not _AVAILABLE:
        return False
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            if enabled:
                winreg.SetValueEx(
                    key, _APP_NAME, 0, winreg.REG_SZ, _launch_command()
                )
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                except FileNotFoundError:
                    pass  # já estava desativado
        return True
    except OSError:
        return False
