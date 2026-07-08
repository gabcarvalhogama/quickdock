; ==========================================================================
;  QuickDock - script do instalador (Inno Setup 6)
; ==========================================================================
;  Gera dist\installer\QuickDockSetup.exe: um instalador que coloca o
;  QuickDock em "Arquivos de Programas", cria atalhos no Menu Iniciar (e,
;  opcionalmente, na Área de Trabalho), registra um desinstalador em
;  "Adicionar/Remover programas" e pode ativar o início com o Windows.
;
;  Pré-requisitos:
;    1) dist\QuickDock.exe já compilado (rode build.bat antes).
;    2) Inno Setup 6 instalado (https://jrsoftware.org/isdl.php).
;  Depois é só rodar:  build_installer.bat  (ou abrir este .iss no Inno Setup).
;
;  Observação: os dados do usuário (atalhos + configurações) ficam em
;  %APPDATA%\QuickDock e NÃO são removidos ao desinstalar.
; ==========================================================================

#define MyAppName "QuickDock"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Gabriel Carvalho"
#define MyAppURL "https://github.com/gabcarvalhogama/quickdock"
#define MyAppExeName "QuickDock.exe"

[Setup]
; AppId identifica o produto entre versões — NÃO mude (senão o instalador
; trata a nova versão como um programa diferente na hora de atualizar).
AppId={{A7C4E2F1-3B9D-4E6A-8F52-1D0C7B9E4A23}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
; Instala em C:\Program Files\QuickDock (requer administrador).
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
OutputDir=dist\installer
OutputBaseFilename=QuickDockSetup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; Fecha o QuickDock automaticamente se estiver aberto durante instalar/atualizar.
CloseApplications=yes

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar um atalho na Área de Trabalho"; GroupDescription: "Atalhos adicionais:"

[Files]
Source: "dist\QuickDock.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; Observação: o "Iniciar com o Windows" é feito DENTRO do app (menu → Iniciar
; com o Windows), que grava na chave Run do usuário atual de forma correta.
; Evita-se fazer isso aqui porque o instalador roda elevado (admin) e uma
; gravação em HKCU nesse contexto pode ir para o perfil errado.

[Run]
; Oferece abrir o app ao final — rodando como o usuário normal (não elevado).
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; \
    Flags: nowait postinstall skipifsilent runasoriginaluser
