; Inno Setup script: one installer for the helper app + the Premiere panel.
; Built on GitHub Actions (see .github/workflows/build.yml).

#define AppName "Hinglish Edit"
#define AppVersion GetEnv("HE_VERSION")
#if AppVersion == ""
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{6F2C1A7E-3B9D-4C55-9A61-2B7E5C9D1A40}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=A-Zone Media Productions
DefaultDirName={autopf}\HinglishEdit
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=admin
OutputDir=..\out
OutputBaseFilename=HinglishEdit-Setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
UninstallDisplayName={#AppName}

[Tasks]
Name: "desktopicon"; Description: "Desktop shortcut for the helper"; GroupDescription: "Shortcuts:"
Name: "autostart"; Description: "Start the helper automatically when Windows starts"; GroupDescription: "Startup:"; Flags: unchecked

[Files]
Source: "..\helper\dist\HinglishEditHelper\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\HinglishEdit.ccx"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\README.md"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\Hinglish Edit Helper"; Filename: "{app}\HinglishEditHelper.exe"; WorkingDir: "{app}"
Name: "{group}\Uninstall Hinglish Edit"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Hinglish Edit Helper"; Filename: "{app}\HinglishEditHelper.exe"; WorkingDir: "{app}"; Tasks: desktopicon
Name: "{userstartup}\Hinglish Edit Helper"; Filename: "{app}\HinglishEditHelper.exe"; WorkingDir: "{app}"; Tasks: autostart

[Run]
Filename: "{app}\HinglishEditHelper.exe"; Description: "Start the Hinglish Edit helper now"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{code:UpiaPath}"; Parameters: "/remove ""Hinglish Edit"""; Flags: runhidden skipifdoesntexist; RunOnceId: "RemovePanel"

[Code]
function UpiaPath(Param: String): String;
begin
  Result := ExpandConstant('{commoncf64}\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe');
  if not FileExists(Result) then
    Result := ExpandConstant('{commoncf32}\Adobe\Adobe Desktop Common\RemoteComponents\UPI\UnifiedPluginInstallerAgent\UnifiedPluginInstallerAgent.exe');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  Code: Integer;
  Upia, Ccx: String;
begin
  if CurStep = ssPostInstall then
  begin
    Upia := UpiaPath('');
    Ccx := ExpandConstant('{app}\HinglishEdit.ccx');
    if FileExists(Upia) and Exec(Upia, '/install "' + Ccx + '"', '', SW_HIDE, ewWaitUntilTerminated, Code) then
    begin
      Log('UPIA exit code: ' + IntToStr(Code));
      if Code <> 0 then
        MsgBox('Adobe''s plugin installer reported code ' + IntToStr(Code) + '.' + #13#10 +
               'If "Hinglish Edit" does not appear in Premiere under Window > UXP Plugins after a restart,' + #13#10 +
               'double-click this file to install it:' + #13#10 + Ccx, mbInformation, MB_OK);
    end
    else
      MsgBox('The helper is installed, but the Premiere panel could not be installed automatically.' + #13#10#13#10 +
             'Please double-click this file to install it:' + #13#10 + Ccx + #13#10#13#10 +
             '(Creative Cloud must be installed. Close Premiere first.)', mbInformation, MB_OK);
  end;
end;
