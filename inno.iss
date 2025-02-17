#define FileHandle
#define MyAppVersion

#expr FileHandle = FileOpen('version.txt')
#if FileHandle == 0
  #error 'Failed to open version.txt'
#endif

#expr MyAppVersion = Trim(FileRead(FileHandle))
#expr FileClose(FileHandle)

[Setup]
AppName=VIPrestore
AppVersion={#MyAppVersion}
AppId={{D9E7A34D-FE6C-AAAA-A4D2-AB7E3A9F4B99}}
DefaultDirName={userpf}\VIPrestore
DefaultGroupName=VIPrestore
UninstallDisplayIcon={app}\VIPrestore.exe
OutputBaseFilename="VIPrestore Installer v{#MyAppVersion}"
Compression=lzma2
CompressionThreads=10
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=logos\viprestore_icon.ico
OutputDir=dist\VIPrestore {#MyAppVersion}
PrivilegesRequired=lowest

; Uncomment these to make it a silent installer
; DisableDirPage=yes
; DisableProgramGroupPage=yes

[Files]
Source: "dist\VIPrestore {#MyAppVersion}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "logos\viprestore_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{userprograms}\VIPrestore\VIPrestore"; Filename: "{app}\VIPrestore.exe"; WorkingDir: "{app}"
Name: "{userprograms}\VIPrestore\Uninstall VIPrestore"; Filename: "{uninstallexe}"; IconFilename: "{app}\viprestore_icon.ico"

[Run]
Filename: "{app}\VIPrestore.exe"; Description: "Launch VIPrestore"; Flags: nowait postinstall skipifsilent

[Code]
var
  IsUpgrade: Boolean;
  UpgradePage: TWizardPage;
  UninstallOption: TRadioButton;
  UpgradeOption: TRadioButton;
  ErrorCode: Integer;

function InitializeSetup(): Boolean;
begin
  // Detect existing installation
  IsUpgrade := RegKeyExists(HKEY_CURRENT_USER, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{{D9E7A34D-FE6C-AAAA-A4D2-AB7E3A9F4B99}_is1}');
  Result := True;  // Proceed with installation
end;

procedure InitializeWizard();
begin
  if IsUpgrade then
  begin
    // Create a custom page
    UpgradePage := CreateCustomPage(wpWelcome, 'Existing Installation Detected', 'VIPrestore is already installed on your computer. What would you like to do?');

    // Add radio buttons for options
    UpgradeOption := TRadioButton.Create(WizardForm);
    UpgradeOption.Parent := UpgradePage.Surface;
    UpgradeOption.Caption := 'Upgrade VIPrestore to version ' + ExpandConstant('{appversion}');
    UpgradeOption.Top := 20;
    UpgradeOption.Left := 0;
    UpgradeOption.Width := WizardForm.ClientWidth;
    UpgradeOption.Checked := True;  // Default to Upgrade

    UninstallOption := TRadioButton.Create(WizardForm);
    UninstallOption.Parent := UpgradePage.Surface;
    UninstallOption.Caption := 'Uninstall VIPrestore';
    UninstallOption.Top := UpgradeOption.Top + UpgradeOption.Height + 10;
    UninstallOption.Left := 0;
    UninstallOption.Width := WizardForm.ClientWidth;
  end;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  // Skip installation pages if uninstalling
  if IsUpgrade and UninstallOption.Checked and ((PageID = wpSelectDir) or (PageID = wpSelectProgramGroup) or (PageID = wpReady)) then
    Result := True
  else
    Result := False;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True; // Allow to proceed by default

  if IsUpgrade and (CurPageID = UpgradePage.ID) then
  begin
    if UninstallOption.Checked then
    begin
      // Confirm uninstallation
      if MsgBox('Are you sure you want to uninstall VIPrestore?', mbConfirmation, MB_YESNO) = IDYES then
      begin
        // Run the uninstaller
        if ShellExec('', ExpandConstant('{uninstallexe}'), '/VERYSILENT /NORESTART', '', SW_SHOWNORMAL, ewWaitUntilTerminated, ErrorCode) then
        begin
          // After uninstallation, exit the setup
          MsgBox('VIPrestore has been uninstalled.', mbInformation, MB_OK);
          Result := False; // Prevent moving to the next page
          Abort(); // Exit the setup
        end
        else
        begin
          MsgBox('Uninstallation failed. Error code: ' + IntToStr(ErrorCode), mbError, MB_OK);
          Result := False; // Stay on the current page
        end;
      end
      else
      begin
        // User canceled uninstallation, stay on the same page
        Result := False;
      end;
    end
    else if UpgradeOption.Checked then
    begin
      // Proceed with the upgrade
      // Optionally, add any upgrade-specific code here
    end;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if (CurStep = ssInstall) and IsUpgrade and UpgradeOption.Checked then
  begin
    MsgBox('Upgrading VIPrestore to version ' + ExpandConstant('{appversion}'), mbInformation, MB_OK);
  end;
end;
