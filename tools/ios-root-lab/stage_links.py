#!/usr/bin/env python3
"""stage_links.py plan|apply [--root MNT --image IMG] [--out DIR] [--project-additions]
Port de la logica de tools/a5xelte-stage-ios-root.sh (L83-125) y tools/mkiosroot.sh (L89-128) sobre los arboles ya copiados:
  - hardlinks de la dyld shared cache del cryptex OS en System/Library/Caches/com.apple.dyld/
  - hardlink (o symlink copiado) en la raiz de cada fichero del cryptex OS/App sin equivalente en el root OS
  - [--project-additions] artefactos DEL PROYECTO (no de Apple): private/var/db/{diagnostics,uuidtext,...}/.migrated (uid 272) y
    private/var/keybags/systembag.kb (plist de teclas ficticias 'SWEET'); se listan aparte en stage_project_added.txt.
plan : solo manifiestos (no toca nada): escribe out/stage_plan.json, out/stage_ignore.txt (extras tolerados en la verificacion de os).
apply: exige guard (root + imagen loop de laboratorio); crea los enlaces y artefactos con propietario/modo explicitos."""
import sys, os, json, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q3lib import *
import guard
DYLD = 'System/Library/Caches/com.apple.dyld'
CRY = {'OS': 'systemos', 'App': 'appos'}
PRE = 'private/preboot/Cryptexes'
LOGD = [('private/var/db/diagnostics', 0o751), ('private/var/db/uuidtext', 0o755), ('private/var/db/diagnostics/timesync', 0o755)]
KEYBAG = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
          '<plist version="1.0"><dict><key>KeyBagKeys</key><data>U1dFRVQ=</data></dict></plist>\n')

def plan(project):
    import posixpath
    osm = {d['path']: d for d in load_manifest('os')}
    cm = {c: load_manifest(v) for c, v in CRY.items()}
    # universo de existencia en la IMAGEN: manifiesto os + cryptex bajo private/preboot/Cryptexes/{OS,App}/ + enlaces ya planificados
    exist = {p: d['type'] for p, d in osm.items()}
    exist[''] = 'dir'
    for c in cm:
        for d in cm[c]: exist['%s/%s/%s' % (PRE, c, d['path'])] = d['type']
    sym = {p: d['target'] for p, d in osm.items() if d['type'] == 'lnk'}
    for c in cm:
        for d in cm[c]:
            if d['type'] == 'lnk': sym['%s/%s/%s' % (PRE, c, d['path'])] = d['target']
    def resolve(path, depth=0, follow_last=True):
        """sigue symlinks como el kernel (absolutos relativos a la raiz de la imagen); devuelve ruta final o None (bucle/colgante)"""
        if depth > 40: return None
        comps = [c for c in path.split('/') if c]
        cur = ''
        for i, c in enumerate(comps):
            nxt = (cur + '/' + c) if cur else c
            if nxt in sym and (i < len(comps) - 1 or follow_last):
                t = sym[nxt]
                base = t.lstrip('/') if t.startswith('/') else posixpath.join(posixpath.dirname(nxt), t)
                rest = comps[i + 1:]
                np = posixpath.normpath(posixpath.join(base, *rest)) if rest else posixpath.normpath(base)
                return resolve('' if np == '.' else np, depth + 1, follow_last)
            cur = nxt
        return cur
    created = {}                                          # dest -> tipo
    def e_or_L(path):                                     # [[ -e path || -L path ]]
        if path in created: return True
        if resolve(path, follow_last=False) in sym or path in sym: return True      # es symlink (colgante o no)
        r = resolve(path)
        return r is not None and (r in exist or r in created)
    links = []; dirs_new = []; resolved_through_symlink = []
    for d in cm['OS']:                                    # dyld cache: stage L91-94 (ficheros regulares directamente en el directorio)
        if d['type'] == 'reg' and d['path'].startswith(DYLD + '/') and '/' not in d['path'][len(DYLD) + 1:]:
            links.append(dict(cry='OS', rel=d['path'], dest=d['path'], kind='reg', inode=d['inode'], dyld=True)); created[d['path']] = 'reg'
    for c in ('OS', 'App'):                               # stage L97-111 (`[[ -e $target || -L $target ]] && continue`)
        for d in cm[c]:
            if d['type'] == 'dir' or d['path'].startswith(DYLD + '/'): continue
            if e_or_L(d['path']): continue
            parent = posixpath.dirname(d['path'])
            if parent and resolve(parent) != parent: resolved_through_symlink.append(d['path'])      # el padre pasaria por un symlink: ln escribiria en otro sitio
            links.append(dict(cry=c, rel=d['path'], dest=d['path'], kind=d['type'], inode=d['inode'], target=d.get('target'))); created[d['path']] = d['type']
    have_dirs = {p for p, t in exist.items() if t == 'dir' and not p.startswith(PRE)}
    for l in links:
        p = l['dest']
        for a in ancestors(p)[::-1]:
            if a not in have_dirs and a not in dirs_new and a not in sym: dirs_new.append(a)
    for l in links:
        p = l['dest']
        for a in ancestors(p)[::-1]:
            if a not in have_dirs and a not in dirs_new: dirs_new.append(a)
    for a in ('private/preboot', PRE, PRE + '/OS', PRE + '/App'):           # presentes en el arbol copiado de los cryptex
        pass
    proj = dict(dirs=[], files=[])
    if project:
        for p, m in LOGD:
            proj['dirs'].append(dict(path=p, uid=272, gid=272, mode=m)); proj['files'].append(dict(path=p + '/.migrated', uid=272, gid=272, mode=0o644, data=''))
        proj['dirs'].append(dict(path='private/var/keybags', uid=0, gid=0, mode=0o700))
        proj['files'].append(dict(path='private/var/keybags/systembag.kb', uid=0, gid=0, mode=0o600, data=KEYBAG))
    return dict(links=links, dirs_new=dirs_new, project=proj, os_paths=len(osm), resolved_through_symlink=resolved_through_symlink)

def ignore_list(pl):
    ig = [PRE + '/']                                       # los cryptex completos se verifican con su propio manifiesto
    ig += [l['dest'] for l in pl['links']] + pl['dirs_new']
    ig += [d['path'] for d in pl['project']['dirs']] + [f['path'] for f in pl['project']['files']]
    return sorted(set(ig))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('mode', choices=['plan', 'apply']); ap.add_argument('--root'); ap.add_argument('--image'); ap.add_argument('--out', default=os.path.join(Q3, 'out'))
    ap.add_argument('--project-additions', action='store_true'); ap.add_argument('--test-fakeroot', action='store_true'); a = ap.parse_args()
    pl = plan(a.project_additions)
    st = collections.Counter(l['kind'] for l in pl['links']); print(json.dumps(dict(enlaces=len(pl['links']), por_tipo=dict(st), dirs_nuevos=len(pl['dirs_new']),
          proyecto_dirs=len(pl['project']['dirs']), proyecto_ficheros=len(pl['project']['files']), padres_via_symlink=len(pl['resolved_through_symlink']))))
    if a.mode == 'plan':
        os.makedirs(a.out, exist_ok=True)
        json.dump(pl, open(os.path.join(a.out, 'stage_plan.json'), 'w'), indent=0)
        open(os.path.join(a.out, 'stage_ignore.txt'), 'w', encoding='utf-8', errors='surrogateescape').write('\n'.join(ignore_list(pl)) + '\n')
        open(os.path.join(a.out, 'stage_project_added.txt'), 'w').write('\n'.join([d['path'] for d in pl['project']['dirs']] + [f['path'] for f in pl['project']['files']]) + '\n')
        return
    if not a.root: sys.exit('apply exige --root')
    guard.assert_lab_mount(a.root, a.image or '', test_fakeroot=a.test_fakeroot)
    os.chdir(a.root); n = collections.Counter()
    for d in pl['dirs_new']:
        os.makedirs(d, exist_ok=True); os.chown(d, 0, 0); os.chmod(d, 0o755); n['dirs'] += 1
    for l in pl['links']:
        src = '%s/%s/%s' % (PRE, l['cry'], l['rel']); dst = l['dest']
        if os.path.lexists(dst): sys.exit('STAGE: destino ya existe: ' + dst)
        if l['kind'] == 'lnk': os.symlink(os.readlink(src), dst); n['symlinks'] += 1
        else: os.link(src, dst); n['hardlinks'] += 1
    for d in pl['project']['dirs']:
        os.makedirs(d['path'], exist_ok=True); os.chown(d['path'], d['uid'], d['gid']); os.chmod(d['path'], d['mode']); n['proj_dirs'] += 1
    for f in pl['project']['files']:
        with open(f['path'], 'w') as fh: fh.write(f['data'])
        os.chown(f['path'], f['uid'], f['gid']); os.chmod(f['path'], f['mode']); n['proj_files'] += 1
    os.sync() if hasattr(os, 'sync') else None
    print(json.dumps(dict(n)))
main()
