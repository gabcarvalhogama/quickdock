"""Ponto de entrada do QuickDock.

Execute com::

    python main.py

Inicia a barra de atalhos e entra no laço principal da interface.
"""

from __future__ import annotations

import sys


def main() -> int:
    # Importa aqui (e não no topo) para que a mensagem de erro de dependência
    # ausente seja clara, sem um traceback gigante.
    try:
        from quickdock.dock import Dock
    except ModuleNotFoundError as exc:  # dependência faltando
        print(
            "Erro ao importar dependências:\n"
            f"  {exc}\n\n"
            "Instale as dependências com:\n"
            "  pip install -r requirements.txt",
            file=sys.stderr,
        )
        return 1

    app = Dock()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
