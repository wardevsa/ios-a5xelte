#!/usr/bin/env python3
"""Comprobación de sintaxis y tipos del código de kernel de DROP v2, sin XNU.

  python3 -I xnu/drop-v2/test/check_kernel_syntax.py

Extrae de xnu/patches/0334-herolte-drop-v2.patch (o de patches-proposed/) la imagen resultante de bsd/dev/herolte_drop.c y la compila
(solo -fsyntax-only) contra test/kstub/kstub.h: cabeceras SIMULADAS con las firmas copiadas de XNU 8796.141.3.
Cubre errores de tipos, de número de argumentos y los avisos que XNU trata como error (-Wmissing-prototypes,
-Wshorten-64-to-32, -Wcast-qual...). NO sustituye a una compilación real de XNU: no valida nombres de KPI que
no estén en el simulacro, ni flags del kernel, ni el enlazado.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DROP = os.path.join(HERE, '..')
PATCH = next(p for p in (os.path.join(DROP, '..', 'patches', '0334-herolte-drop-v2.patch'),
                         os.path.join(DROP, 'patches-proposed', '0334-herolte-drop-v2.patch'))
             if os.path.exists(p))
FORWARD = ['sys/param.h', 'sys/systm.h', 'sys/errno.h', 'sys/fcntl.h', 'sys/stat.h', 'sys/proc.h',
           'sys/vnode_internal.h', 'sys/namei.h', 'sys/kauth.h', 'sys/mount.h', 'kern/kalloc.h',
           'kern/clock.h', 'kern/thread.h', 'pexpert/pexpert.h']


def post_image(patch_text, name):
    """Contenido final de `name` según el parche (líneas ' ' y '+' de su sección)."""
    out, inside, started = [], False, False
    for line in patch_text.split('\n'):
        if line.startswith('diff --git '):
            inside = line.endswith(' b/' + name)
            started = False
            continue
        if not inside:
            continue
        if line.startswith('@@'):
            started = True
            continue
        if started and line[:1] in (' ', '+'):
            out.append(line[1:])
    if not out:
        raise SystemExit(f'{name} no aparece en el parche')
    return '\n'.join(out) + '\n'


def main():
    text = open(PATCH).read()
    with tempfile.TemporaryDirectory(prefix='kcheck-') as d:
        stub, src = os.path.join(d, 'stub'), os.path.join(d, 'src')
        os.makedirs(src)
        for h in FORWARD:
            os.makedirs(os.path.join(stub, os.path.dirname(h)), exist_ok=True)
            open(os.path.join(stub, h), 'w').write('#include "../kstub.h"\n' if '/' in h else '#include "kstub.h"\n')
        shutil.copy(os.path.join(HERE, 'kstub', 'kstub.h'), os.path.join(stub, 'kstub.h'))
        for f in ('herolte_drop_core.c', 'herolte_drop_core.h'):
            shutil.copy(os.path.join(DROP, f), src)
        open(os.path.join(src, 'herolte_drop.c'), 'w').write(post_image(text, 'bsd/dev/herolte_drop.c'))
        bad = 0
        for unit, extra in (('herolte_drop.c', []),
                            ('herolte_drop_core.c', ['-Wshorten-64-to-32', '-Wcast-qual', '-Wmissing-prototypes',
                                                     '-Wstrict-prototypes', '-Wmissing-variable-declarations',
                                                     '-Wconditional-uninitialized', '-Wsign-compare'])):
            cmd = ['clang', '-std=gnu11', '-fsyntax-only', '-DKERNEL', '-DARM64_BOARD_CONFIG_HEROLTE',
                   '-I' + stub, '-I' + src, '-Wall', '-Wextra', '-Werror'] + extra + [os.path.join(src, unit)]
            r = subprocess.run(cmd, capture_output=True, text=True)
            msgs = [re.sub(r'^.*/(src|stub)/', '', l) for l in r.stderr.splitlines() if 'error' in l or 'warning' in l]
            print(f'  [{"OK" if r.returncode == 0 else "FALLA"}] {unit}')
            for m in msgs[:12]:
                print('      ' + m)
            bad += r.returncode != 0
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
