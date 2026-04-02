; TSUNAMI — Inno Setup Installer
; Produces a standard Windows installer with progress bar, Start Menu entry,
; desktop shortcut, and Add/Remove Programs uninstaller.
;
; Build: iscc tsunami.iss
; Requires: Inno Setup 6+ (https://jrsoftware.org/issetup.php)
;
; The installer bundles the repo + runs setup.ps1 post-install to download
; models and llama-server. This keeps the installer small (~5MB) while the
; heavy downloads (~7GB) happen with a visible progress bar in PowerShell.

#define MyAppName "Tsunami"
#define MyAppVersion "1.0"
#define MyAppPublisher "gobbleyourdong"
#define MyAppURL "https://github.com/gobbleyourdong/tsunami"
#define MyAppExeName "tsu.ps1"

[Setup]
AppId={{B8F3A2E1-7D4C-4F8A-9E2B-1A3C5D7E9F0B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputBaseFilename=TsunamiSetup
SetupIconFile=..\desktop\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
OutputDir=output

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
; Bundle the entire repo (excluding heavy stuff)
Source: "..\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs; Excludes: "*.gguf,node_modules,dist,.git,__pycache__,workspace,.venv,models,installer\output"

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\tsu.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\desktop\icon.ico"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\tsu.ps1"""; WorkingDir: "{app}"; IconFilename: "{app}\desktop\icon.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checked

[Run]
; Run setup.ps1 after install — downloads models, llama-server, deps
Filename: "powershell.exe"; Parameters: "-ExecutionPolicy Bypass -File ""{app}\setup.ps1"""; Description: "Download models and dependencies (~7GB)"; Flags: postinstall nowait shellexec; StatusMsg: "Setting up Tsunami..."

[UninstallDelete]
Type: filesandordirs; Name: "{app}\models"
Type: filesandordirs; Name: "{app}\llama-server"
Type: filesandordirs; Name: "{app}\workspace"
Type: filesandordirs; Name: "{app}\node_modules"
Type: filesandordirs; Name: "{app}\.venv"

[Code]
function InitializeSetup(): Boolean;
var
  Msg: String;
begin
  Msg := 'Tsunami will install the app (~5MB) then download AI models (~7GB).' + Chr(13) + Chr(10) +
    Chr(13) + Chr(10) +
    'Requirements:' + Chr(13) + Chr(10) +
    '  - Windows 10 or later' + Chr(13) + Chr(10) +
    '  - 8GB+ RAM (or GPU VRAM)' + Chr(13) + Chr(10) +
    '  - ~10GB free disk space' + Chr(13) + Chr(10) +
    '  - Internet connection for model download' + Chr(13) + Chr(10) +
    Chr(13) + Chr(10) +
    'Continue?';
  Result := MsgBox(Msg, mbConfirmation, MB_YESNO) = IDYES;
end;
