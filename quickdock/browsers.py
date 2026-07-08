"""Detecção do Google Chrome e dos seus perfis.

- :func:`find_chrome`     -> caminho do ``chrome.exe`` (ou ``None``).
- :func:`chrome_profiles` -> lista de ``(pasta, nome_amigavel)`` dos perfis,
  lida do arquivo ``Local State`` do Chrome. Assim o usuário escolhe o perfil
  pelo nome (ex.: "Gabriel") em vez de decorar a pasta (ex.: "Profile 1").

O Chrome abre uma URL num perfil específico com::

    chrome.exe --profile-directory="Profile 1" "https://exemplo.com"
"""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import List, Optional, Tuple


def find_chrome() -> Optional[str]:
    """Retorna o caminho do ``chrome.exe`` ou ``None`` se não encontrar."""
    candidates: List[str] = []
    for var in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        base = os.environ.get(var)
        if base:
            candidates.append(os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"))

    # registro do Windows (App Paths)
    try:
        import winreg

        for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            try:
                with winreg.OpenKey(
                    root, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe"
                ) as key:
                    value, _ = winreg.QueryValueEx(key, None)
                    if value:
                        candidates.append(value)
            except OSError:
                continue
    except Exception:  # noqa: BLE001
        pass

    found = shutil.which("chrome")
    if found:
        candidates.append(found)

    for path in candidates:
        if path and os.path.isfile(path):
            return path
    return None


def _user_data_dir() -> Optional[Path]:
    local = os.environ.get("LocalAppData")
    if not local:
        return None
    d = Path(local) / "Google" / "Chrome" / "User Data"
    return d if d.exists() else None


def chrome_profiles() -> List[Tuple[str, str]]:
    """Lista de ``(pasta, nome_amigavel)`` dos perfis do Chrome.

    Retorna ``[]`` se o Chrome/os perfis não forem encontrados (a interface
    então cai para um campo de texto).
    """
    d = _user_data_dir()
    if not d:
        return []

    profiles: List[Tuple[str, str]] = []
    state = d / "Local State"
    if state.exists():
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
            cache = data.get("profile", {}).get("info_cache", {})
            for folder, info in cache.items():
                name = (info or {}).get("name") or folder
                profiles.append((folder, name))
        except (OSError, json.JSONDecodeError, ValueError):
            profiles = []

    # fallback: varre pastas "Default" / "Profile N"
    if not profiles:
        try:
            for sub in d.iterdir():
                if sub.is_dir() and (sub.name == "Default" or sub.name.startswith("Profile ")):
                    profiles.append((sub.name, sub.name))
        except OSError:
            pass

    profiles.sort(key=_profile_sort_key)
    return profiles


def _profile_sort_key(item: Tuple[str, str]):
    folder = item[0]
    if folder == "Default":
        return (0, 0)
    if folder.startswith("Profile "):
        try:
            return (1, int(folder.split()[1]))
        except (ValueError, IndexError):
            return (2, 0)
    return (3, 0)
