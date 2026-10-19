#!/usr/bin/env bash
# Chạy từ gốc repo sau build.sh -> MagicHub-x86_64.AppImage
set -e
A=build/MagicHub.AppDir
rm -rf "$A" && mkdir -p "$A/usr/bin"
cp -r dist/MagicHub/. "$A/usr/bin/"
cat > "$A/AppRun" <<'R'
#!/bin/sh
exec "$(dirname "$(readlink -f "$0")")/usr/bin/MagicHub" "$@"
R
chmod +x "$A/AppRun"
cat > "$A/MagicHub.desktop" <<'D'
[Desktop Entry]
Type=Application
Name=MagicHub
Exec=MagicHub
Icon=magichub
Categories=Utility;
D
python3 - "$A/magichub.png" <<'P'
import sys
from PIL import Image, ImageDraw
im = Image.new("RGBA", (256, 256)); d = ImageDraw.Draw(im)
for i, c in enumerate(("#e5484d", "#30a46c", "#3e63dd")):
    d.pieslice((16, 16, 240, 240), -90 + i * 120, 30 + i * 120, fill=c)
d.ellipse((88, 88, 168, 168), fill="white"); im.save(sys.argv[1])
P
ARCH=x86_64 ${APPIMAGETOOL:-appimagetool} "$A" MagicHub-x86_64.AppImage
