"""Ícone na bandeja do sistema (área de notificação).

Permite que o QuickDock rode em segundo plano: mesmo com a barra escondida,
o ícone na bandeja mantém o app acessível (mostrar/esconder, busca rápida,
configurações e sair) e evita que ele ocupe um botão na barra de tarefas.

Depende da biblioteca opcional ``pystray``.  Se ela não estiver instalada (ou
o registro falhar), o app continua funcionando normalmente — apenas sem o
ícone na bandeja.

Como os callbacks do ``pystray`` rodam na *thread* do ícone e o Tkinter não é
*thread-safe*, cada ação é enfileirada numa ``queue`` e consumida pela thread
da interface via :meth:`TrayIcon.drain` — mesmo padrão do
:class:`quickdock.hotkeys.HotkeyManager`.
"""

from __future__ import annotations

import queue
import threading
from typing import List, Optional

from PIL import Image, ImageDraw

try:  # dependência opcional
    import pystray  # type: ignore

    _PYSTRAY_AVAILABLE = True
except Exception:  # noqa: BLE001
    pystray = None  # type: ignore
    _PYSTRAY_AVAILABLE = False


# Comandos enfileirados para a thread da interface.
CMD_TOGGLE = "toggle"
CMD_SEARCH = "search"
CMD_SETTINGS = "settings"
CMD_QUIT = "quit"


def _make_image(size: int = 64) -> Image.Image:
    """Gera o ícone da bandeja: um "dock" minimalista (fundo azul, botões)."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # fundo arredondado (mesmo azul dos avatares de URL)
    draw.rounded_rectangle([2, 2, size - 3, size - 3], radius=size // 4, fill="#3b82f6")

    # três "botões" brancos empilhados, evocando a própria barra
    margin = size // 4
    btn_w = size - 2 * margin
    btn_h = max(4, size // 10)
    gap = max(4, size // 12)
    total = 3 * btn_h + 2 * gap
    y = (size - total) // 2
    for _ in range(3):
        draw.rounded_rectangle(
            [margin, y, margin + btn_w, y + btn_h], radius=btn_h // 2, fill="#ffffff"
        )
        y += btn_h + gap
    return img


class TrayIcon:
    """Ícone na bandeja do sistema, rodando numa thread própria."""

    def __init__(self, tooltip: str = "QuickDock") -> None:
        self._queue: "queue.Queue[str]" = queue.Queue()
        self._icon = None
        self._thread: Optional[threading.Thread] = None
        self._tooltip = tooltip

    @property
    def available(self) -> bool:
        """Indica se a biblioteca ``pystray`` pôde ser carregada."""
        return _PYSTRAY_AVAILABLE

    # ------------------------------------------------------------------ #
    def start(self) -> bool:
        """Cria e inicia o ícone numa thread daemon.  Retorna ``True`` se ok."""
        if not _PYSTRAY_AVAILABLE or self._icon is not None:
            return False
        try:
            menu = pystray.Menu(
                pystray.MenuItem(
                    "Mostrar / Esconder", self._enqueue(CMD_TOGGLE), default=True
                ),
                pystray.MenuItem("Busca rápida", self._enqueue(CMD_SEARCH)),
                pystray.MenuItem("Configurações…", self._enqueue(CMD_SETTINGS)),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Sair", self._enqueue(CMD_QUIT)),
            )
            self._icon = pystray.Icon("QuickDock", _make_image(), self._tooltip, menu)
            self._thread = threading.Thread(target=self._icon.run, daemon=True)
            self._thread.start()
            return True
        except Exception:  # noqa: BLE001
            self._icon = None
            return False

    def _enqueue(self, command: str):
        """Fábrica de callbacks que apenas enfileiram o comando (thread-safe)."""

        def handler(icon=None, item=None) -> None:  # assinatura do pystray
            self._queue.put(command)

        return handler

    def drain(self) -> List[str]:
        """Consome os comandos pendentes; deve ser chamada pela thread da UI."""
        commands: List[str] = []
        try:
            while True:
                commands.append(self._queue.get_nowait())
        except queue.Empty:
            pass
        return commands

    def stop(self) -> None:
        """Encerra o ícone da bandeja."""
        if self._icon is not None:
            try:
                self._icon.stop()
            except Exception:  # noqa: BLE001
                pass
            self._icon = None
