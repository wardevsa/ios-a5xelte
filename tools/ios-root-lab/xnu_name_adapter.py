#!/usr/bin/env python3
"""xnu_name_adapter: ÚNICO punto de traducción de nombres del generador del root (D-0017, D-0020, D-0024).

Linux escribe un nombre en HFS+ descomponiéndolo con SU tabla; XNU espera la suya (Unicode 3.2, sin los rangos que no se descomponen).
Si el ÁRBOL DE STAGING ya trae los nombres en forma XNU (tools/hfsplus-names/xnu_names_stage.py apply) y el MANIFIESTO se lee con esta
misma traducción, todos los scripts de esta carpeta (apply_meta_img, stage_links, verify_meta, relink, hfsx_check) hablan de los mismos nombres.
  - se traduce cada componente con xnu_nfd; el ':' POSIX NO se toca (lo convierte en '/' el propio hfsplus de Linux)
  - los destinos de los enlaces simbólicos NO se traducen (son contenido, no nombres del catálogo)
  - se EXCLUYEN las rutas de IOS_LAB_EXCLUDE (por defecto $IOS_ROOT_LAB/out/xnu_excluded_paths.txt; KI-0006): los nombres que, ya en forma
    XNU, la tabla de Linux volvería a cambiar (necesitarían nodecompose, que está descartado). Si el fichero no existe se ABORTA: nunca se asume "sin exclusiones".
CLI: python3 -I xnu_name_adapter.py rsync-exclude-file OUTDIR   -> escribe OUTDIR/xnu_rsync_exclude.txt (rutas ancladas con '/' para rsync) y lo imprime."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'hfsplus-names'))
import hfs_names as _h


def translate_component(c):
    if c.isascii(): return c
    if any(0xD800 <= ord(ch) <= 0xDFFF for ch in c): return c        # bytes no UTF-8 (surrogateescape): no se tocan
    return _h.xnu_nfd(c)


def translate_path(p): return '/'.join(translate_component(c) for c in p.split('/'))


def load_exclusions(path=None):
    path = path or os.environ.get('IOS_LAB_EXCLUDE') or os.path.join(os.environ.get('IOS_ROOT_LAB', ''), 'out', 'xnu_excluded_paths.txt')
    if not os.path.isfile(path): sys.exit('xnu_name_adapter: falta la lista de exclusiones %r (xnu_names_stage.py plan --ko ... --exclude-list); no se asume "sin exclusiones"' % path)
    return {l.rstrip('\n') for l in open(path, encoding='utf-8', errors='surrogateescape') if l.strip()}


def is_excluded(p, excluded): return p in excluded or any(p.startswith(x + '/') for x in excluded)


def translate_manifest(entries, excluded):
    """Copia del manifiesto con 'path' en forma XNU, sin las rutas excluidas; conserva la original en 'path_manifest'. Comprueba que no hay colisiones."""
    out, seen = [], {}
    for d in entries:
        if is_excluded(d['path'], excluded): continue
        e = dict(d); e['path_manifest'] = d['path']; e['path'] = translate_path(d['path'])
        if e['path'] in seen and seen[e['path']] != d['path']: sys.exit('xnu_name_adapter: colisión de nombres tras traducir: %r y %r' % (seen[e['path']], d['path']))
        seen[e['path']] = d['path']; out.append(e)
    return out


def main(argv):
    if len(argv) == 3 and argv[1] == 'rsync-exclude-file':
        ex = load_exclusions(); f = os.path.join(argv[2], 'xnu_rsync_exclude.txt')
        with open(f, 'w', encoding='utf-8', errors='surrogateescape') as o:
            for x in sorted(ex): o.write('/' + x + '\n')
        print(f); return 0
    print(__doc__); return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
