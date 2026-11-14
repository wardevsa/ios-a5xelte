#!/usr/bin/env python3
"""verify_stage.py ROOT : comprueba los artefactos de stage_links (plan en out/stage_plan.json) sobre un arbol/imagen montada:
cada enlace de la raiz es el MISMO inodo (st_dev,st_ino) que su original del cryptex (o un symlink con el mismo destino); los artefactos del
proyecto existen con propietario/modo/contenido esperados. exit 1 si hay discrepancias."""
import sys, os, json, collections, stat
root = sys.argv[1]; pl = json.load(open(os.path.join(os.environ.get('IOS_ROOT_LAB') or sys.exit('IOS_ROOT_LAB'), 'out', 'stage_plan.json')))
res = collections.Counter(); bad = []
def emit(c, p, d=''):
    res[c] += 1
    if c != 'OK' and len(bad) < 15: bad.append((c, p, d))
for l in pl['links']:
    src = os.path.join(root, 'private/preboot/Cryptexes', l['cry'], l['rel']); dst = os.path.join(root, l['dest'])
    if not os.path.lexists(dst): emit('MISSING', l['dest']); continue
    if l['kind'] == 'lnk':
        emit('OK' if os.path.islink(dst) and os.readlink(dst) == os.readlink(src) else 'TARGET', l['dest']); continue
    a, b = os.lstat(src), os.lstat(dst)
    emit('OK' if (a.st_dev, a.st_ino) == (b.st_dev, b.st_ino) and stat.S_ISREG(b.st_mode) else 'NOT-SAME-INODE', l['dest'])
for d in pl['dirs_new']:
    p = os.path.join(root, d); emit('OK' if os.path.isdir(p) else 'MISSING-DIR', d)
for d in pl['project']['dirs']:
    p = os.path.join(root, d['path'])
    if not os.path.isdir(p): emit('MISSING-DIR', d['path']); continue
    s = os.lstat(p); emit('OK' if (s.st_uid, s.st_gid, s.st_mode & 0o7777) == (d['uid'], d['gid'], d['mode']) else 'META', d['path'], '%d:%d %o' % (s.st_uid, s.st_gid, s.st_mode & 0o7777))
for f in pl['project']['files']:
    p = os.path.join(root, f['path'])
    if not os.path.isfile(p): emit('MISSING', f['path']); continue
    s = os.lstat(p); ok = (s.st_uid, s.st_gid, s.st_mode & 0o7777) == (f['uid'], f['gid'], f['mode']) and open(p).read() == f['data']
    emit('OK' if ok else 'META/CONTENT', f['path'])
print(json.dumps(dict(res)))
for b in bad: print('  ', *b)
sys.exit(1 if set(res) - {'OK'} else 0)
