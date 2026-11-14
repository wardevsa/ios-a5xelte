#!/usr/bin/env python3
"""¿Aplicó el CI el parche pedido? Lee el log de una ejecución del workflow xnu (solo lectura, usa `gh`).

  python3 -I xnu/drop-v2/deviceday/ci_check.py OWNER/REPO RUN_ID [PARCHE=0337-herolte-drop-v2]

PARCHE es el NOMBRE COMPLETO del parche (con o sin `.patch`). Un número suelto (`0334`, `0334-`) casa con varios
parches si dos series comparten número (T-0009: 0332 y 0334 están duplicados con origin/herolte) y daría un falso
"aplicado": por eso un identificador ambiguo se rechaza (salida 2) en lugar de adivinar.

El script de compilación del CI (darwin-xnu-build) SALTA con un aviso los parches que no aplican y sigue: sin esta
comprobación un 0334 roto pasaría desapercibido y el kernel saldría con el 0333/0332 anterior. Sale con 1 si el parche
pedido no consta como aplicado o consta como saltado. Lista también cualquier otro parche saltado.
"""
import io
import re
import subprocess
import sys
import zipfile


DEFAULT_PATCH = '0337-herolte-drop-v2'


def normalise(name):
    return name[:-6] if name.endswith('.patch') else name


def verdict(applied, skipped, wanted):
    """-> (código de salida, líneas). 0 aplicado y no saltado; 1 no aplicado o saltado; 2 identificador ambiguo/incompleto.
    `applied` y `skipped` son nombres de fichero .patch (skipped: lista de (nombre, motivo))."""
    wanted = normalise(wanted)
    seen = sorted({normalise(a) for a in applied} | {normalise(s[0]) for s in skipped})
    if re.fullmatch(r'\d{4}-?', wanted):
        cand = [n for n in seen if n.startswith(wanted[:4] + '-')]
        return 2, [f'identificador incompleto {wanted!r}: pasa el nombre completo del parche (visto en el log: {cand or "ninguno"})']
    matches = [n for n in seen if n == wanted]
    if not matches:
        same_number = [n for n in seen if n[:4] == wanted[:4]]
        return 1, [f'{wanted}: NO consta en el log (mismo número en el log: {same_number or "ninguno"})']
    ok_applied = any(normalise(a) == wanted for a in applied)
    ok_skipped = any(normalise(s[0]) == wanted for s in skipped)
    line = f'{wanted}: ' + ('APLICADO' if ok_applied else 'NO consta como aplicado') + (' y SALTADO' if ok_skipped else '')
    return (0 if ok_applied and not ok_skipped else 1), [line]


def main():
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    repo, run = sys.argv[1], sys.argv[2]
    wanted = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_PATCH
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
    code, lines = verdict(applied, skipped, wanted)
    print('\n'.join(lines))
    return code


if __name__ == '__main__':
    sys.exit(main())
