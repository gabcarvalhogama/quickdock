"""Carregamento e geração de ícones.

Estratégia para obter o ícone de um atalho, em ordem de prioridade:

1. Se o atalho define um caminho de imagem (``icon``) válido -> carrega com
   Pillow.
2. Se a ação aponta para um arquivo/programa existente -> tenta extrair o
   ícone nativo do arquivo via ``pywin32``.
3. Caso contrário -> gera um "avatar" com a inicial do nome, colorido de
   acordo com o tipo da ação.

Todos os ícones são retornados como ``CTkImage`` (compatível com HiDPI) e
ficam em cache para não reprocessar a cada redesenho.
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict, Optional, Tuple

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageFont

from .models import (
    ACTION_CHROME,
    ACTION_COMMAND,
    ACTION_FILE,
    ACTION_FOLDER,
    ACTION_GROUP,
    ACTION_MACRO,
    ACTION_MULTI_URL,
    ACTION_PROGRAM,
    ACTION_SCRIPT,
    ACTION_URL,
    Shortcut,
)

# Extração de ícone nativo é opcional (depende de pywin32).
try:
    import win32con  # type: ignore
    import win32gui  # type: ignore
    import win32ui  # type: ignore

    _WIN32_AVAILABLE = True
except Exception:  # noqa: BLE001
    _WIN32_AVAILABLE = False


# --------------------------------------------------------------------------- #
# Paleta de cores por tipo de ação (para os avatares gerados)
# --------------------------------------------------------------------------- #
_TYPE_COLORS: Dict[str, str] = {
    ACTION_URL: "#3b82f6",        # azul
    ACTION_MULTI_URL: "#6366f1",  # índigo
    ACTION_PROGRAM: "#22c55e",    # verde
    ACTION_FOLDER: "#f59e0b",     # âmbar
    ACTION_FILE: "#14b8a6",       # teal
    ACTION_COMMAND: "#64748b",    # cinza-azulado
    ACTION_SCRIPT: "#a855f7",     # roxo
    ACTION_MACRO: "#ec4899",      # rosa
    ACTION_GROUP: "#0ea5e9",      # ciano (grupo de sub-botões)
    ACTION_CHROME: "#4285F4",     # azul Google
}
_DEFAULT_COLOR = "#3b82f6"

_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\segoeuib.ttf",
    r"C:\Windows\Fonts\seguisb.ttf",
    r"C:\Windows\Fonts\segoeui.ttf",
    r"C:\Windows\Fonts\arialbd.ttf",
)

#: fonte de emojis coloridos do Windows (Segoe UI Emoji, tabela COLR).
_EMOJI_FONT_CANDIDATES = (
    r"C:\Windows\Fonts\seguiemj.ttf",
)

#: prefixo usado no campo ``icon`` para indicar um emoji (ex.: ``emoji:🚀``).
EMOJI_PREFIX = "emoji:"


# Cache de CTkImage por (chave, tamanho).  Mantém referências vivas para
# que o Tk não colete as imagens.
_ctk_cache: Dict[Tuple[str, int], ctk.CTkImage] = {}


# --------------------------------------------------------------------------- #
# API pública
# --------------------------------------------------------------------------- #
def get_icon(shortcut: Shortcut, size: int) -> ctk.CTkImage:
    """Retorna um ``CTkImage`` para o atalho, usando cache."""
    key = _cache_key(shortcut, size)
    cached = _ctk_cache.get(key)
    if cached is not None:
        return cached

    pil = _build_pil_icon(shortcut, size)
    image = ctk.CTkImage(light_image=pil, dark_image=pil, size=(size, size))
    _ctk_cache[key] = image
    return image


def clear_cache() -> None:
    """Limpa o cache (após editar/adicionar atalhos)."""
    _ctk_cache.clear()


def get_emoji_image(char: str, size: int) -> ctk.CTkImage:
    """``CTkImage`` de um emoji isolado (usado pelo seletor de emojis)."""
    key = (f"{EMOJI_PREFIX}pick:{char}", size)
    cached = _ctk_cache.get(key)
    if cached is not None:
        return cached
    pil = _emoji_icon(char, size) or _letter_avatar(char or "?", size, _DEFAULT_COLOR)
    image = ctk.CTkImage(light_image=pil, dark_image=pil, size=(size, size))
    _ctk_cache[key] = image
    return image


# --------------------------------------------------------------------------- #
# Construção da imagem PIL
# --------------------------------------------------------------------------- #
def _cache_key(shortcut: Shortcut, size: int) -> Tuple[str, int]:
    base = shortcut.icon or shortcut.target or shortcut.name
    return (f"{shortcut.type}|{base}|{shortcut.name}", size)


def _build_pil_icon(shortcut: Shortcut, size: int) -> Image.Image:
    icon = (shortcut.icon or "").strip()

    # 1a) emoji explícito (prefixo ``emoji:``)
    if icon.startswith(EMOJI_PREFIX):
        img = _emoji_icon(icon[len(EMOJI_PREFIX):], size)
        if img is not None:
            return img
    # 1b) emoji "colado direto" no campo (sem prefixo)
    elif icon and _looks_like_emoji(icon) and not os.path.exists(os.path.expandvars(icon)):
        img = _emoji_icon(icon, size)
        if img is not None:
            return img
    # 1c) imagem explícita (caminho de arquivo)
    elif icon:
        img = _load_image_file(os.path.expandvars(icon), size)
        if img is not None:
            return img

    # 2) ícone nativo do arquivo/programa
    if shortcut.type in (ACTION_PROGRAM, ACTION_FILE):
        path = os.path.expandvars(os.path.expanduser(shortcut.target))
        if path and os.path.exists(path):
            img = _extract_file_icon(path, size)
            if img is not None:
                return img

    # 2b) tipo Chrome sem ícone -> usa o logo do próprio Chrome
    if shortcut.type == ACTION_CHROME:
        from .browsers import find_chrome

        chrome = find_chrome()
        if chrome:
            img = _extract_file_icon(chrome, size)
            if img is not None:
                return img

    # 3) avatar com inicial
    return _letter_avatar(shortcut.name, size, _TYPE_COLORS.get(shortcut.type, _DEFAULT_COLOR))


def _looks_like_emoji(text: str) -> bool:
    """Heurística: string curta contendo símbolos/emoji (> setas)."""
    text = text.strip()
    if not text or len(text) > 8:
        return False
    return any(ord(ch) > 0x2190 for ch in text)


# --------------------------------------------------------------------------- #
# Emoji colorido (Segoe UI Emoji, via Pillow embedded_color)
# --------------------------------------------------------------------------- #
def _emoji_icon(char: str, size: int) -> Optional[Image.Image]:
    char = (char or "").strip()
    if not char:
        return None
    font = _load_emoji_font(int(size * 0.86))
    if font is None:
        return None

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    try:  # renderização colorida (COLR/CBDT)
        bbox = draw.textbbox((0, 0), char, font=font, embedded_color=True)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1])
        draw.text(pos, char, font=font, embedded_color=True)
    except Exception:  # noqa: BLE001 - fallback monocromático
        try:
            bbox = draw.textbbox((0, 0), char, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            pos = ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1])
            draw.text(pos, char, font=font, fill="#ffffff")
        except Exception:  # noqa: BLE001
            return None

    return img if img.getbbox() is not None else None


@lru_cache(maxsize=16)
def _load_emoji_font(px: int):
    for candidate in _EMOJI_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, px)
        except OSError:
            continue
    return None


def _load_image_file(path: str, size: int) -> Optional[Image.Image]:
    try:
        if not path or not os.path.exists(path):
            return None
        img = Image.open(path).convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        # centraliza em um quadrado exato
        canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        canvas.paste(img, ((size - img.width) // 2, (size - img.height) // 2), img)
        return canvas
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Avatar com a inicial do nome
# --------------------------------------------------------------------------- #
def _letter_avatar(name: str, size: int, color: str) -> Image.Image:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    radius = max(4, size // 4)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=color)

    letter = (name.strip()[:1] or "?").upper()
    font = _load_font(int(size * 0.55))
    # centraliza a letra
    try:
        bbox = draw.textbbox((0, 0), letter, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        pos = ((size - tw) / 2 - bbox[0], (size - th) / 2 - bbox[1])
    except Exception:  # noqa: BLE001 - fontes antigas
        tw, th = draw.textsize(letter, font=font)  # type: ignore[attr-defined]
        pos = ((size - tw) / 2, (size - th) / 2)
    draw.text(pos, letter, font=font, fill="#ffffff")
    return img


@lru_cache(maxsize=16)
def _load_font(px: int) -> ImageFont.FreeTypeFont:
    for candidate in _FONT_CANDIDATES:
        try:
            return ImageFont.truetype(candidate, px)
        except OSError:
            continue
    return ImageFont.load_default()


# --------------------------------------------------------------------------- #
# Extração do ícone nativo via pywin32
# --------------------------------------------------------------------------- #
def _extract_file_icon(path: str, size: int) -> Optional[Image.Image]:
    """Extrai o ícone embutido de um .exe/arquivo e converte para PIL.

    Retorna ``None`` silenciosamente se algo falhar (pywin32 ausente,
    arquivo sem ícone, etc.).
    """
    if not _WIN32_AVAILABLE:
        return None

    large = small = None
    try:
        large, small = win32gui.ExtractIconEx(path, 0)
        handles = (large or []) + (small or [])
        if not handles:
            return None
        hicon = (large or small)[0]

        hdc_screen = win32gui.GetDC(0)
        hdc = win32ui.CreateDCFromHandle(hdc_screen)
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, size, size)
        mem_dc = hdc.CreateCompatibleDC()
        mem_dc.SelectObject(hbmp)
        win32gui.DrawIconEx(
            mem_dc.GetSafeHdc(), 0, 0, hicon, size, size, 0, None, win32con.DI_NORMAL
        )

        bmpstr = hbmp.GetBitmapBits(True)
        img = Image.frombuffer("RGBA", (size, size), bmpstr, "raw", "BGRA", 0, 1)

        # limpeza de GDI
        win32gui.ReleaseDC(0, hdc_screen)
        mem_dc.DeleteDC()
        hdc.DeleteDC()
        win32gui.DeleteObject(hbmp.GetHandle())

        # se a imagem veio totalmente transparente, considera falha
        if img.getbbox() is None:
            return None
        return img
    except Exception:  # noqa: BLE001
        return None
    finally:
        for h in list(large or []) + list(small or []):
            try:
                win32gui.DestroyIcon(h)
            except Exception:  # noqa: BLE001
                pass
