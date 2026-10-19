; PhDF Windows installer (Inno Setup 6). Built by .github/workflows/release.yml:
;   iscc /DAppVersion=0.7.0 /DSourceDir=<folder with PhDF.exe> packaging\windows\phdf.iss
; Installs for the current user (no admin needed), adds a Start Menu entry, "Open with PhDF" for
; PDF / EPUB / Markdown and registers PhDF so it can be chosen as the default PDF app.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\PhDF"
#endif

[Setup]
AppId={{6F0E6C2E-3B7A-4C55-9D0B-5E1A7C2B9F41}
AppName=PhDF
AppVersion={#AppVersion}
AppVerName=PhDF {#AppVersion}
AppPublisher=PhDF
AppPublisherURL=https://github.com/barjs-havingfun/PhDF
AppSupportURL=https://github.com/barjs-havingfun/PhDF/issues
DefaultDirName={autopf}\PhDF
DefaultGroupName=PhDF
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile=..\..\LICENSE
SetupIconFile=..\icons\phdf.ico
UninstallDisplayIcon={app}\PhDF.exe
OutputDir=..\..\dist
OutputBaseFilename=PhDF-{#AppVersion}-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ChangesAssociations=yes
CloseApplications=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

; An update only overwrites files: empty the old bundle first so files the new version no
; longer has don't stay behind (the user's data lives in %APPDATA%\PhDF, not here).
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PhDF"; Filename: "{app}\PhDF.exe"
Name: "{autodesktop}\PhDF"; Filename: "{app}\PhDF.exe"; Tasks: desktopicon

[Registry]
; One document type for PDF, EPUB and Markdown, opened with PhDF.
Root: HKA; Subkey: "Software\Classes\PhDF.Document"; ValueType: string; ValueData: "PhDF document"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\PhDF.Document\DefaultIcon"; ValueType: string; ValueData: "{app}\PhDF.exe,0"
Root: HKA; Subkey: "Software\Classes\PhDF.Document\shell\open\command"; ValueType: string; ValueData: """{app}\PhDF.exe"" ""%1"""
; "Open with PhDF" (doesn't take over existing defaults).
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PhDF.Document"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.epub\OpenWithProgids"; ValueType: string; ValueName: "PhDF.Document"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.md\OpenWithProgids"; ValueType: string; ValueName: "PhDF.Document"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\PhDF.exe\SupportedTypes"; ValueType: string; ValueName: ".pdf"; ValueData: ""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\PhDF.exe\SupportedTypes"; ValueType: string; ValueName: ".epub"; ValueData: ""
Root: HKA; Subkey: "Software\Classes\Applications\PhDF.exe\SupportedTypes"; ValueType: string; ValueName: ".md"; ValueData: ""
; Registered application: lets Windows Settings → Default apps list PhDF (Settings → General →
; "Make PhDF the default PDF app" opens that page).
Root: HKA; Subkey: "Software\PhDF\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "PhDF"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\PhDF\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Reader-first PDF and EPUB app with Markdown notes"
Root: HKA; Subkey: "Software\PhDF\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "PhDF.Document"
Root: HKA; Subkey: "Software\PhDF\Capabilities\FileAssociations"; ValueType: string; ValueName: ".epub"; ValueData: "PhDF.Document"
Root: HKA; Subkey: "Software\PhDF\Capabilities\FileAssociations"; ValueType: string; ValueName: ".md"; ValueData: "PhDF.Document"
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "PhDF"; ValueData: "Software\PhDF\Capabilities"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\PhDF.exe"; Description: "Start PhDF"; Flags: nowait postinstall skipifsilent

[Code]
// Uninstalling: ask whether PhDF's own data (reading positions, bookmarks, Library, settings)
// should go too. The user's PDFs and notes are never touched.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\PhDF');
    if DirExists(DataDir) and not UninstallSilent then
      if MsgBox('Also delete PhDF''s data (reading positions, bookmarks, Library and settings)?' + #13#10 +
                'Your PDFs and notes are not touched.', mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
        DelTree(DataDir, True, True, True);
  end;
end;
