#!/bin/sh
# herolte-video-frames.sh VIDEO OUTDIR [EVERY_N]
# Extrae fotogramas de un vídeo del arranque (sin instalar nada: GStreamer + PIL) como PNG numerados en OUTDIR y crea
# OUTDIR/contact-sheet-NNN.png con 24 fotogramas por hoja (cada EVERY_N-ésimo, 1 por defecto) para mirarlos sin transcripción.
# Solo lee VIDEO; nunca toca el teléfono. No sube nada.
set -eu
V=${1:?uso: $0 VIDEO OUTDIR [EVERY_N]}; O=${2:?uso: $0 VIDEO OUTDIR [EVERY_N]}; N=${3:-1}
[ -f "$V" ] || { echo "no existe $V" >&2; exit 2; }
[ ! -e "$O" ] || [ -z "$(ls -A "$O" 2>/dev/null)" ] || { echo "ABORTA: $O no está vacío" >&2; exit 3; }
mkdir -p "$O"
gst-launch-1.0 -q filesrc location="$V" ! decodebin ! videoconvert ! pngenc ! multifilesink location="$O/f%05d.png" >/dev/null
python3 -I - "$O" "$N" <<'PY'
import sys, glob, os
from PIL import Image
o, n = sys.argv[1], int(sys.argv[2])
fr = sorted(glob.glob(os.path.join(o, 'f*.png')))[::n]
print(len(fr), 'fotogramas (cada', n, ')')
W, H, cols = 270, 480, 6
for s in range(0, len(fr), 24):
    sheet = Image.new('RGB', (W * cols, H * 4), 'gray')
    for k, p in enumerate(fr[s:s + 24]):
        im = Image.open(p).convert('RGB'); im.thumbnail((W, H))
        sheet.paste(im, ((k % cols) * W, (k // cols) * H))
    out = os.path.join(o, 'contact-sheet-%03d.png' % (s // 24))
    sheet.save(out); print(out)
PY
