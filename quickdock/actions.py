"""Execução das ações dos atalhos.

Este módulo concentra toda a lógica de *executar algo* — abrir URLs,
programas, pastas, arquivos, comandos, scripts e macros.  Ele não conhece
nada da interface: recebe um :class:`~quickdock.models.Shortcut` (ou um
:class:`~quickdock.models.MacroStep`) e o executa, reportando erros através
de um callback opcional.

Macros rodam em uma thread separada para que as esperas (``wait``) não
travem a interface.
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
import threading
import time
import webbrowser
from typing import Callable, List, Optional

from .models import (
    ACTION_CHROME,
    ACTION_COMMAND,
    ACTION_FILE,
    ACTION_FOLDER,
    ACTION_MACRO,
    ACTION_MULTI_URL,
    ACTION_PROGRAM,
    ACTION_SCRIPT,
    ACTION_URL,
    MacroStep,
    Shortcut,
)

# SW_SHOWMINNOACTIVE: janela minimizada sem roubar o foco.
_SW_SHOWMINNOACTIVE = 7

# Cria um console novo e dedicado para o processo filho.  Essencial para
# comandos/CLIs interativos (ex.: "claude"): sem isso, o processo tenta usar
# o console do QuickDock — que pode não existir (.exe sem console) ou estar
# ocupado pela interface (quando iniciado por um terminal).
_CREATE_NEW_CONSOLE = getattr(subprocess, "CREATE_NEW_CONSOLE", 0x00000010)


class ActionExecutor:
    """Executa ações de forma isolada da interface gráfica.

    Parameters
    ----------
    on_error:
        Callback ``(mensagem: str) -> None`` chamado quando algo falha.
        A interface usa isso para exibir uma caixa de erro.
    """

    def __init__(self, on_error: Optional[Callable[[str], None]] = None) -> None:
        self._on_error = on_error

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def execute(self, shortcut: Shortcut) -> None:
        """Executa um atalho de acordo com o seu tipo."""
        try:
            if shortcut.type == ACTION_MACRO:
                self._run_macro(shortcut.steps)
            else:
                self._dispatch(
                    action_type=shortcut.type,
                    target=shortcut.target,
                    targets=shortcut.targets,
                    args=shortcut.args,
                    cwd=shortcut.working_directory,
                    minimized=shortcut.minimized,
                    browser_profile=shortcut.browser_profile,
                )
        except Exception as exc:  # noqa: BLE001 - reportamos tudo à UI
            self._report(f"Falha ao executar '{shortcut.name}':\n{exc}")

    # ------------------------------------------------------------------ #
    # Despacho por tipo
    # ------------------------------------------------------------------ #
    def _dispatch(
        self,
        action_type: str,
        target: str,
        targets: List[str],
        args: str,
        cwd: str,
        minimized: bool,
        browser_profile: str = "",
    ) -> None:
        if action_type == ACTION_URL:
            self._open_url(target)
        elif action_type == ACTION_MULTI_URL:
            urls = targets or self._split_lines(target)
            self._open_urls(urls)
        elif action_type == ACTION_CHROME:
            urls = targets or self._split_lines(target)
            self._open_chrome(urls, browser_profile)
        elif action_type == ACTION_PROGRAM:
            self._open_program(target, args, cwd, minimized)
        elif action_type == ACTION_FOLDER:
            self._open_folder(target)
        elif action_type == ACTION_FILE:
            self._open_file(target)
        elif action_type == ACTION_COMMAND:
            self._run_command(target, args, cwd, minimized)
        elif action_type == ACTION_SCRIPT:
            self._run_script(target, args, cwd, minimized)
        else:
            self._report(f"Tipo de ação desconhecido: {action_type}")

    # ------------------------------------------------------------------ #
    # Primitivas de ação
    # ------------------------------------------------------------------ #
    def _open_url(self, url: str) -> None:
        url = url.strip()
        if url:
            webbrowser.open(url, new=2)

    def _open_urls(self, urls: List[str]) -> None:
        for url in urls:
            self._open_url(url)

    def _open_chrome(self, urls: List[str], profile: str) -> None:
        """Abre uma ou mais URLs no Chrome, num perfil específico."""
        urls = [u.strip() for u in urls if u.strip()]
        if not urls:
            return
        from .browsers import find_chrome

        chrome = find_chrome()
        if not chrome:
            self._report(
                "Google Chrome não foi encontrado no computador.\n"
                "Instale o Chrome ou use a ação 'Abrir URL' comum."
            )
            return
        profile = (profile or "Default").strip()
        # várias URLs abrem como abas na janela do perfil escolhido
        cmd = [chrome, f"--profile-directory={profile}"] + urls
        subprocess.Popen(cmd)

    def _open_program(self, target: str, args: str, cwd: str, minimized: bool) -> None:
        path = self._expand(target)
        cmd = [path] + self._split_args(args)
        subprocess.Popen(
            cmd,
            cwd=self._norm_cwd(cwd),
            startupinfo=self._startupinfo(minimized),
            close_fds=False,
        )

    def _open_folder(self, target: str) -> None:
        path = self._expand(target)
        # ``explorer`` aceita caminhos e também locais especiais (ex.: shell:).
        os.startfile(path)  # type: ignore[attr-defined]

    def _open_file(self, target: str) -> None:
        os.startfile(self._expand(target))  # type: ignore[attr-defined]

    def _run_command(self, command: str, args: str, cwd: str, minimized: bool) -> None:
        full = command
        if args.strip():
            full = f"{command} {args}"
        # Abre um console novo e dedicado que permanece aberto (``cmd /k``):
        # torna comandos interativos (ex.: "claude") utilizáveis e deixa a
        # saída visível em vez de piscar e sumir.
        subprocess.Popen(
            f"cmd /k {full}",
            cwd=self._norm_cwd(cwd),
            creationflags=_CREATE_NEW_CONSOLE,
            startupinfo=self._startupinfo(minimized),
        )

    def _run_script(self, target: str, args: str, cwd: str, minimized: bool) -> None:
        path = self._expand(target)
        ext = os.path.splitext(path)[1].lower()
        arglist = self._split_args(args)

        if ext == ".py":
            interpreter = self._python_executable()
            cmd = [interpreter, path] + arglist
        elif ext == ".ps1":
            cmd = [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                path,
            ] + arglist
        elif ext in (".bat", ".cmd"):
            # ``/k`` mantém o console aberto para ver a saída/erros do script.
            cmd = ["cmd", "/k", path] + arglist
        else:
            # extensão desconhecida: deixa o Windows decidir
            os.startfile(path)  # type: ignore[attr-defined]
            return

        # Scripts rodam no próprio console dedicado (saída visível, sem
        # conflito com o console do QuickDock).
        subprocess.Popen(
            cmd,
            cwd=self._norm_cwd(cwd),
            creationflags=_CREATE_NEW_CONSOLE,
            startupinfo=self._startupinfo(minimized),
        )

    # ------------------------------------------------------------------ #
    # Macros
    # ------------------------------------------------------------------ #
    def _run_macro(self, steps: List[MacroStep]) -> None:
        """Roda os passos em background, respeitando as esperas."""

        def worker() -> None:
            for step in steps:
                try:
                    self._dispatch(
                        action_type=step.type,
                        target=step.target,
                        targets=step.targets,
                        args=step.args,
                        cwd=step.working_directory,
                        minimized=step.minimized,
                        browser_profile=step.browser_profile,
                    )
                except Exception as exc:  # noqa: BLE001
                    self._report(f"Erro em passo da macro:\n{exc}")
                if step.wait and step.wait > 0:
                    time.sleep(step.wait)

        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    # Auxiliares
    # ------------------------------------------------------------------ #
    @staticmethod
    def _expand(value: str) -> str:
        """Expande variáveis de ambiente (%VAR%) e ``~``."""
        if not value:
            return ""
        return os.path.expandvars(os.path.expanduser(value.strip()))

    @classmethod
    def _norm_cwd(cls, cwd: str):
        """Normaliza a pasta inicial e valida sua existência.

        Converte barras normais em ``\\`` (o ``CreateProcess`` do Windows é
        exigente), expande variáveis e garante que a pasta existe — do
        contrário, lança um erro claro em vez de falhar de forma silenciosa.
        Retorna ``None`` quando nenhuma pasta foi informada (usa a padrão).
        """
        expanded = cls._expand(cwd)
        if not expanded:
            return None
        path = os.path.normpath(expanded)
        if not os.path.isdir(path):
            raise NotADirectoryError(f"Pasta inicial não encontrada:\n{path}")
        return path

    @staticmethod
    def _split_args(args: str) -> List[str]:
        """Divide a string de argumentos respeitando aspas (estilo Windows)."""
        if not args or not args.strip():
            return []
        try:
            return shlex.split(args, posix=False)
        except ValueError:
            return args.split()

    @staticmethod
    def _split_lines(value: str) -> List[str]:
        return [line.strip() for line in (value or "").splitlines() if line.strip()]

    @staticmethod
    def _python_executable() -> str:
        """Interpretador Python a usar para scripts .py.

        Quando empacotado (PyInstaller) ``sys.executable`` é o próprio app,
        então recorremos ao ``python`` do PATH.
        """
        if getattr(sys, "frozen", False):
            return "python"
        return sys.executable or "python"

    @staticmethod
    def _startupinfo(minimized: bool):
        """Cria um ``STARTUPINFO`` para abrir minimizado quando pedido."""
        if not minimized:
            return None
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = _SW_SHOWMINNOACTIVE
        return si

    def _report(self, message: str) -> None:
        if self._on_error:
            self._on_error(message)
        else:  # fallback discreto no console
            print(f"[QuickDock] {message}", file=sys.stderr)
