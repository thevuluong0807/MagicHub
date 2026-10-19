; Inno Setup. Build từ gốc repo sau PyInstaller: iscc /DVersion=0.4.0 packaging\windows\MagicHub.iss -> MagicHub-Setup.exe
#ifndef Version
  #define Version "0.0.0"
#endif
[Setup]
AppName=MagicHub
AppVersion={#Version}
AppPublisher=MagicHub
DefaultDirName={autopf}\MagicHub
DefaultGroupName=MagicHub
PrivilegesRequired=lowest
OutputDir=..\..
OutputBaseFilename=MagicHub-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayName=MagicHub
LicenseFile=..\..\LICENSE

[Tasks]
Name: "autostart"; Description: "Tự chạy MagicHub khi đăng nhập Windows"
Name: "sendto"; Description: "Thêm MagicHub vào menu chuột phải → Send to"

[Files]
Source: "..\..\dist\MagicHub\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{group}\MagicHub"; Filename: "{app}\MagicHub.exe"
Name: "{userstartup}\MagicHub"; Filename: "{app}\MagicHub.exe"; Tasks: autostart
Name: "{usersendto}\MagicHub"; Filename: "{app}\MagicHub.exe"; Parameters: "menu"; Tasks: sendto

[Run]
Filename: "{app}\MagicHub.exe"; Description: "Chạy MagicHub ngay"; Flags: nowait postinstall skipifsilent
