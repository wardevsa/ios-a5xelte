#!/bin/bash
# HEROLTE: the stock wallpapers' pictures are HEIC (HEVC), and this phone has no HEVC decoder: ImageIO opens
# them and draws nothing (CollectionsPoster, boot-heic: 0 of 2500560 pixels). Each .HEIC under the root's
# /Library/Wallpaper is made PNG in place, keeping its name: the .ca packages name their assets by file name,
# and ImageIO knows a PNG by its first bytes. Run on macOS (sips) as root with the HFSX root mounted read-write.
#
#   herolte-wallpaper-png.sh ROOT [OUT]
#
# With OUT, the converted pictures of the wallpapers this screen uses (375w-812h, given our screen class by
# herolte-tune-ios-root.sh) are also copied to OUT/walls/N with OUT/walls/list ("N /Library/Wallpaper/..."),
# for the drop zone: hero-run puts them over the HEIC files of a root made before this script.
set -euo pipefail
root=$1 out=${2:-}
[ -d "$root/Library/Wallpaper" ] || { echo "no $root/Library/Wallpaper"; exit 1; }
if [ -n "$out" ]; then
    mkdir -p "$out/walls"
    : > "$out/walls/list"
fi
made=0 kept=0 n=0
while IFS= read -r -d '' heic; do
    tmp="$heic.png.tmp"
    if /usr/bin/sips -s format png "$heic" --out "$tmp" >/dev/null 2>&1 && [ -s "$tmp" ]; then
        mv -f "$tmp" "$heic"
        chmod 644 "$heic"
        made=$((made + 1))
        rel=${heic#"$root"}
        if [ -n "$out" ] && [[ "$rel" == *375w-812h* ]]; then
            n=$((n + 1))
            cp "$heic" "$out/walls/$n"
            echo "$n $rel" >> "$out/walls/list"
        fi
    else
        rm -f "$tmp"
        kept=$((kept + 1))
        echo "kept as HEIC: ${heic#"$root"}"
    fi
done < <(find "$root/Library/Wallpaper" -iname '*.heic' -print0)
echo "wallpaper pictures made PNG: $made, kept: $kept, for the drop zone: $n"
if [ -n "$out" ]; then
    du -sh "$out/walls"
fi
