"""QuickDock - uma barra de atalhos leve, sempre visível, para Windows.

Pacote principal da aplicação.  A organização em módulos segue uma
separação clara de responsabilidades:

- ``models``          -> estruturas de dados (Shortcut, MacroStep, Settings).
- ``storage``         -> persistência em JSON (carregar/salvar).
- ``actions``         -> execução das ações (URL, programa, script, macro...).
- ``hotkeys``         -> registro do atalho global.
- ``icons``           -> carregamento/geração de ícones (Pillow + pywin32).
- ``tooltip``         -> dica de contexto ao passar o mouse.
- ``shortcut_button`` -> widget de um botão de atalho.
- ``dock``            -> janela principal (barra) e toda a interação.
- ``settings_window`` -> tela de configurações.
- ``editor``          -> diálogos de adicionar/editar atalho e macro.
- ``search``          -> busca rápida sobreposta.
"""

__version__ = "1.0.0"
__all__ = ["__version__"]
