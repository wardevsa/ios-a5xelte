#!/usr/bin/env python3
"""¿Aplicó el CI el parche 0334? Lee el log de una ejecución del workflow xnu (solo lectura, usa `gh`).

  python3 -I xnu/drop-v2/deviceday/ci_check.py OWNER/REPO RUN_ID [PATCH_PREFIX=0334-]

El script de compilación del CI (darwin-xnu-build) SALTA con un aviso los parches que no aplican y sigue: sin esta
comprobación un 0334 roto pasaría desapercibido y el kernel saldría con el 0333/0332 anterior. Sale con 1 si el parche
pedido no consta como aplicado o consta como saltado. Lista también cualquier otro parche saltado.
"""
import io
import re
import subprocess
import sys
import zipfile


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    repo, run = sys.argv[1], sys.argv[2]
    prefix = sys.argv[3] if len(sys.argv) > 3 else '0334-'
    p = subprocess.run(['gh', 'api', f'repos/{repo}/actions/runs/{run}/logs'], capture_output=True)
    if p.returncode != 0:
        raise SystemExit(f'gh failed: {p.stderr.decode(errors="replace").strip()[:200]}')
    z = zipfile.ZipFile(io.BytesIO(p.stdout))
    names = [i.filename for i in sorted(z.infolist(), key=lambda i: -i.file_size) if i.filename.endswith('.txt')]
    text = z.read(names[0]).decode('utf-8', 'replace')
    ansi = re.compile(r'\x1b\[[0-9;]*m')
    applied, skipped = [], []
    for line in text.splitlines():
        line = ansi.sub('', line)
        m = re.search(r'Applying patch: \S*/([^/\s]+\.patch)', line)
        if m:
            applied.append(m.group(1))
        m = re.search(r'Skipping patch \S*/([^/\s:]+\.patch)(.*)', line)
        if m:
            skipped.append((m.group(1), m.group(2).strip()[:110]))
    print(f'parches aplicados: {len(applied)}; saltados: {len(skipped)}')
    ours = [s for s in skipped if re.match(r'\d{4}-', s[0])]
    print(f'  de ellos, de este repositorio (NNNN-*.patch): {len(ours)}; el resto son parches de darwin-xnu-build ya presentes en upstream')
    for name, why in ours:
        print(f'  SALTADO {name} {why}')
    ok_applied = any(a.startswith(prefix) for a in applied)
    ok_skipped = any(s[0].startswith(prefix) for s in skipped)
    print(f'{prefix}*: ' + ('APLICADO' if ok_applied else 'NO consta como aplicado') + (' y SALTADO' if ok_skipped else ''))
    return 0 if ok_applied and not ok_skipped else 1


if __name__ == '__main__':
    sys.exit(main())
