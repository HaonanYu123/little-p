#define MyAppName "Little P"
#define MyAppVersion "0.1.0"
#define MyAppExeName "LittleP.exe"

[Setup]
AppId={{B84C77A4-55E9-4703-8296-BB57F5DD4209}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={autopf}\LittleP
DefaultGroupName={#MyAppName}
PrivilegesRequired=admin
OutputDir=..\output\installer
OutputBaseFilename=LittleP-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Files]
Source: "..\dist\LittleP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加快捷方式："

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
Root: HKCR; Subkey: "littlep"; ValueType: string; ValueName: ""; ValueData: "URL:Little P Protocol"; Flags: uninsdeletekey
Root: HKCR; Subkey: "littlep"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCR; Subkey: "littlep\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCR; Subkey: "littlep\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent
