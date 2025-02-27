#define ReadVersionFromFile(str FileName) \
  Local[0] = FileOpen(FileName), \
  Local[0] == -1 ? \
    (Error("Unable to open version.txt")) : \
    (Local[1] = FileRead(Local[0]), \
     FileClose(Local[0]), \
     Trim(Local[1]))

#define MyVersion ReadVersionFromFile("version.txt")
#define MyAppExeName "VIPrestore " + MyVersion + ".exe"
#define MyAppDirName "VIPrestore " + MyVersion

[Setup]
AppName=VIPrestore
AppVersion={#MyVersion}
AppId={{B08F74EE-9B8C-4D91-92CD-123456789ABC}}
DefaultDirName={commonpf}\VIPrestore
DefaultGroupName=VIPrestore
OutputDir=dist\{#MyAppDirName}
OutputBaseFilename=VIPrestore-{#MyVersion}-Setup
SetupIconFile=logos\viprestore_icon.ico
UninstallDisplayIcon={app}\VIPrestore {#MyVersion}.exe
Compression=lzma2
SolidCompression=yes
UsePreviousAppDir=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
DisableDirPage=auto
WizardImageFile=logos\viprestore_icon.bmp
WizardSmallImageFile=logos\viprestore_icon.bmp

[Files]
Source: "dist\{#MyAppDirName}\*"; DestDir: "{app}"; \
 Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\VIPrestore"; Filename: "{app}\{#MyAppExeName}"; \
 WorkingDir: "{app}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch VIPrestore"; \
 Flags: nowait postinstall skipifsilent
