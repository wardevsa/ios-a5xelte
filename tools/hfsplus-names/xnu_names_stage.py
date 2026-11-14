#!/usr/bin/env python3
"""xnu_names_stage.py: D-0017 (T-0024). Planea (y solo con --apply ejecuta) el renombrado de los ficheros de un árbol de STAGING (ext4, sin sudo,
sin montar nada) a la forma de nombre que XNU espera, `hfs_names.hfs_component`, antes de copiarlos al volumen HFS+.

  python3 -I tools/hfsplus-names/xnu_names_stage.py plan  TREE [--ko hfsplus.ko[.zst]]     # solo lectura; informa
  python3 -I tools/hfsplus-names/xnu_names_stage.py apply TREE [--ko ...]                 # renombra de verdad (rename dentro del mismo directorio)

Seguridad: nunca sigue enlaces simbólicos, no sale de TREE, se niega si hay colisiones o nombres de más de 255 unidades UTF-16, y NO renombra
directorios (solo hojas; si un directorio cambiaría, se aborta). Con --ko informa, para cada nombre, si el `hfsplus` de Linux montado POR DEFECTO
(sin `nodecompose`) lo dejaría tal cual: los que no, necesitan `nodecompose` (un montaje) o quedar fuera. Es el MODELO validado de hfs_names; no un montaje real.
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hfs_names as h


def walk(tree):
    """(dir, name, is_dir) de cada entrada, sin seguir enlaces."""
    for d, dirs, files in os.walk(tree, followlinks=False):
        for n in dirs: yield d, n, True
        for n in files: yield d, n, False


def plan(tree, table=None):
    """-> dict con 'renames' [(dir, old, new)], 'dir_changes', 'collisions', 'too_long', 'needs_nodecompose'."""
    ren, dirs_changed, bydir = [], [], {}
    for d, n, isdir in walk(tree):
        bydir.setdefault(d, []).append(n)
        new = h.xnu_nfd(n)                       # NO hfs_component: el ':' POSIX lo convierte en '/' el propio hfsplus de Linux al escribir
        if new != n:
            (dirs_changed if isdir else ren).append((d, n, new))
    coll = []
    for d, names in bydir.items():
        seen = {}
        for n in names:
            k = h.xnu_nfd(n)
            if k in seen and seen[k] != n: coll.append((d, seen[k], n))
            seen.setdefault(k, n)
        # un nombre renombrado no puede coincidir con otro existente distinto
        existing = set(names)
        for dd, o, nw in ren:
            if dd == d and nw in existing and nw != o: coll.append((d, o, nw))
    long_ = [(d, n) for d, ns in bydir.items() for n in ns if len(h.xnu_nfd(n.replace(':', '/')).encode('utf-16-le')) // 2 > 255]
    needs = []
    if table is not None:
        for d, ns in bydir.items():                       # el nombre FINAL de cada hoja (renombrada o no) frente a la tabla de Linux
            for n in ns:
                if os.path.isdir(os.path.join(d, n)) and not os.path.islink(os.path.join(d, n)): continue
                fin = h.xnu_nfd(n)
                if h.linux_nfd(fin, table) != fin: needs.append((d, n, fin))
    return dict(renames=ren, dir_changes=dirs_changed, collisions=coll, too_long=long_, needs_nodecompose=needs)


def apply(tree, p):
    if p['dir_changes'] or p['collisions'] or p['too_long']: raise SystemExit('NO se aplica: hay directorios que cambiarían, colisiones o nombres demasiado largos')
    root = os.path.realpath(tree)
    for d, o, nw in p['renames']:
        src, dst = os.path.join(d, o), os.path.join(d, nw)
        if os.path.islink(src) or os.path.realpath(d) != d and not os.path.realpath(d).startswith(root): raise SystemExit('se niega a renombrar fuera del árbol o un enlace: %r' % src)
        if os.path.lexists(dst): raise SystemExit('el destino ya existe: %r' % dst)
        os.rename(src, dst)
    return len(p['renames'])


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('mode', choices=['plan', 'apply']); ap.add_argument('tree'); ap.add_argument('--ko'); ap.add_argument('--exclude-list', help='escribe aquí (fichero NUEVO) las rutas relativas que necesitan nodecompose, para excluirlas del copiado (rsync --exclude-from); no borra nada')
    a = ap.parse_args()
    if not os.path.isdir(a.tree) or os.path.islink(a.tree): raise SystemExit('TREE debe ser un directorio real')
    p = plan(a.tree, h.linux_table(a.ko) if a.ko else None)
    print('renombres de hojas: %d | directorios que cambiarían: %d | colisiones: %d | demasiado largos: %d%s' % (len(p['renames']), len(p['dir_changes']), len(p['collisions']), len(p['too_long']),
          (' | necesitan nodecompose aun renombrados: %d' % len(p['needs_nodecompose'])) if a.ko else ''))
    if a.exclude_list:
        if not a.ko: raise SystemExit('--exclude-list necesita --ko')
        with open(a.exclude_list, 'x', encoding='utf-8') as f:
            for d, o, nw in sorted(p['needs_nodecompose']): f.write(os.path.relpath(os.path.join(d, nw if os.path.exists(os.path.join(d, nw)) else o), a.tree) + '\n')
    if a.mode == 'apply': print('renombrados: %d' % apply(a.tree, p))
    return 1 if (p['dir_changes'] or p['collisions'] or p['too_long']) else 0


if __name__ == '__main__':
    sys.exit(main())
