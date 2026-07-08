"""Atalho global de teclado (mostrar/esconder a barra).

Usa a biblioteca ``keyboard``.  Como os callbacks do ``keyboard`` rodam em
uma thread própria e o Tkinter não é *thread-safe*, o disparo é enfileirado
em uma ``queue`` e consumido pela thread principal da interface através de
:meth:`HotkeyManager.drain` (chamada periodicamente pelo dock).

A dependência é opcional: se ``keyboard`` não estiver instalada ou o
registro falhar (por falta de permissão, por exemplo), o aplicativo continua
funcionando normalmente, apenas sem o atalho global.
"""

from __future__ import annotations

import queue
from typing import Optional

try:  # dependência opcional
    import keyboard  # type: ignore
    _KEYBOARD_AVAILABLE = True
except Exception:  # noqa: BLE001
    keyboard = None  # type: ignore
    _KEYBOARD_AVAILABLE = False


class HotkeyManager:
    """Gerencia o registro/desregistro do atalho global."""

    def __init__(self) -> None:
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._handle = None
        self._hotkey: Optional[str] = None
        self.last_error: Optional[str] = None

    @property
    def available(self) -> bool:
        """Indica se a biblioteca ``keyboard`` pôde ser carregada."""
        return _KEYBOARD_AVAILABLE

    # ------------------------------------------------------------------ #
    def register(self, hotkey: str) -> bool:
        """Registra ``hotkey`` (ex.: ``"ctrl+space"``).

        Retorna ``True`` em caso de sucesso.  Substitui qualquer registro
        anterior.
        """
        self.unregister()
        self._hotkey = hotkey
        if not _KEYBOARD_AVAILABLE or not hotkey:
            self.last_error = "Biblioteca 'keyboard' indisponível."
            return False
        try:
            self._handle = keyboard.add_hotkey(  # type: ignore[union-attr]
                hotkey, lambda: self._queue.put("toggle")
            )
            self.last_error = None
            return True
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            self._handle = None
            return False

    def unregister(self) -> None:
        """Remove o atalho atual, se houver."""
        if self._handle is not None and _KEYBOARD_AVAILABLE:
            try:
                keyboard.remove_hotkey(self._handle)  # type: ignore[union-attr]
            except (KeyError, ValueError):
                pass
        self._handle = None

    def drain(self) -> int:
        """Consome os disparos pendentes; retorna quantos ocorreram.

        Deve ser chamada pela thread da interface (via ``after``).
        """
        count = 0
        try:
            while True:
                self._queue.get_nowait()
                count += 1
        except queue.Empty:
            pass
        return count

    def stop(self) -> None:
        """Encerra por completo o hook de teclado."""
        self.unregister()
        if _KEYBOARD_AVAILABLE:
            try:
                keyboard.unhook_all_hotkeys()  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                pass
