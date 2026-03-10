; Inno Setup script for AlphaTW desktop installer
; Build steps:
; 1) powershell -ExecutionPolicy Bypass -File scripts\build_desktop.ps1
; 2) Open this file in Inno Setup and click Build

#define MyAppName "AlphaTW"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "AlphaTW"
#define MyAppExeName "AlphaTW.exe"

[Setup]
AppId={{9A98E978-2B66-4E29-B3F5-9D527D0FBE7A}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist-installer
OutputBaseFilename=AlphaTW-Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "chinesetraditional"; MessagesFile: "compiler:Languages\ChineseTraditional.isl"

[Tasks]
Name: "desktopicon"; Description: "建立桌面捷徑"; GroupDescription: "附加選項:"; Flags: unchecked

[Files]
Source: "..\dist\AlphaTW\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "啟動 {#MyAppName}"; Flags: nowait postinstall skipifsilent
