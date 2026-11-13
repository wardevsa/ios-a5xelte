#!/usr/bin/env python3
"""relink.py MANIFEST_VOL ROOT [--scope F] [--dry-run] [--emit SCRIPT] [--report R.json]
Recompone los hardlinks perdidos por 7z (que extrae cada nombre como una copia). Grupos = ficheros regulares con el mismo
iNode del manifiesto (nlink>1; equivale a sibling links del fs-tree sellado, verificado nlink==nombres==siblings en t04o).
Canonico = primer nombre (orden de bytes) presente. Si algun nombre del grupo difiere en contenido: HARDLINK-DIVERGENT (no se enlaza, exit 1)."""
import sys, os, json, argparse, collections, filecmp
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q3lib import *

def groups(man, scope=None):
    g = collections.defaultdict(list)
    for d in man:
        if d['type'] == 'reg' and d['nlink'] > 1 and (scope is None or d['path'] in scope): g[d['inode']].append(d)
    for v in g.values(): v.sort(key=lambda d: d['path'].encode('utf-8', 'surrogateescape'))
    return g

def plan(man, scope=None):
    """solo desde el manifiesto (sin arbol): comandos ln -f canonico nombre"""
    out = []
    for ino, names in sorted(groups(man, scope).items()):
        for d in names[1:]: out.append('ln -f -- %s %s' % (shq(names[0]['path']), shq(d['path'])))
    return out

def run(man, root, scope=None, dry=False):
    G = groups(man, scope); rep = collections.Counter(); cmds = []; bad = []
    for ino, names in sorted(G.items()):
        present = [d for d in names if os.path.lexists(os.path.join(root, d['path']))]
        rep['grupos'] += 1; rep['nombres_ausentes'] += len(names) - len(present)
        if len(present) < 2: continue
        can = present[0]; cp = os.path.join(root, can['path'])
        for d in present[1:]:
            p = os.path.join(root, d['path'])
            st, sc = os.lstat(p), os.lstat(cp)
            if (st.st_dev, st.st_ino) == (sc.st_dev, sc.st_ino): rep['ya_enlazados'] += 1; continue
            if st.st_size != sc.st_size or not filecmp.cmp(cp, p, shallow=False):
                rep['HARDLINK-DIVERGENT'] += 1; bad.append((can['path'], d['path'])); continue
            cmds.append('ln -f -- %s %s' % (shq(can['path']), shq(d['path'])))
            rep['enlaces_a_crear'] += 1; rep['bytes_recuperados'] += st.st_size
            if not dry:
                tmp = p + '.q3lnk'
                os.link(cp, tmp); os.replace(tmp, p)
    return rep, cmds, bad

if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('vol'); ap.add_argument('root'); ap.add_argument('--scope'); ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--emit'); ap.add_argument('--report'); a = ap.parse_args()
    man = load_manifest(a.vol); rep, cmds, bad = run(man, a.root, read_scope(a.scope), a.dry_run)
    if a.emit: open(a.emit, 'w').write('\n'.join(cmds) + '\n')
    rep = dict(rep); rep['divergentes'] = bad[:20]
    if a.report: json.dump(rep, open(a.report, 'w'), indent=1)
    print(json.dumps(rep)); sys.exit(1 if bad else 0)
