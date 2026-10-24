#define MyAppName "The Watcher"
#define MyAppExe "TheWatcher.exe"
#ifndef MyAppVersion
  #define MyAppVersion "1.1.0"
#endif

[Setup]
AppId={{6D2A5B64-3C9E-4F7B-9A53-8F1E2C7D4B10}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=The Watcher
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\installer_out
OutputBaseFilename=TheWatcher-Setup-Win81
SetupIconFile=..\assets\watcher.ico
UninstallDisplayIcon={app}\{#MyAppExe}
; Windows 8.1 (6.3.9600) o superior, solo 64 bits
MinVersion=6.3.9600
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Tasks]
Name: "desktopicon"; Description: "Crear un icono en el &escritorio"; GroupDescription: "Accesos directos:"; Flags: unchecked
Name: "firewall"; Description: "Permitir The Watcher en el Firewall de Windows (necesario para «Buscar ONVIF»)"; GroupDescription: "Red:"

[Files]
; Todo lo que el programa necesita va dentro: Python, Qt, FFmpeg, runtime de C/C++ de Microsoft.
Source: "..\dist\TheWatcher\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{group}\Diagnóstico de {#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Parameters: "--diagnose"
Name: "{group}\Desinstalar {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#MyAppName}"""; Flags: runhidden; Tasks: firewall
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#MyAppName}"" dir=in action=allow program=""{app}\{#MyAppExe}"" enable=yes profile=private,domain protocol=UDP"; Flags: runhidden; Tasks: firewall; StatusMsg: "Configurando el Firewall de Windows..."
Filename: "{app}\{#MyAppExe}"; Description: "Abrir {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#MyAppName}"""; Flags: runhidden; RunOnceId: "DelFirewallRule"
