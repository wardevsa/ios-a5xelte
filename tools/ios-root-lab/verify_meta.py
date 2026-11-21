#!/usr/bin/env python3
"""verify_meta.py VOL ROOT [--scope F] [--hash] [--report R.jsonl] [--name-policy exact|nfd-equiv] [--skip-time] [--allow-sidecars]
Compara un arbol de laboratorio con el manifiesto (metadatos del arbol sellado; sha256 si existe).  Para uid/gid/modo reales de
Samsung-target se debe ejecutar bajo `fakeroot -i ESTADO -- python3 verify_meta.py ...` (lstat falseado).
Clases: OK MISSING EXTRA SIDECAR TYPE TARGET EMPTY SIZE-MISMATCH FAIL(hash) MODE UID GID TIME HARDLINK-SPLIT HARDLINK-MERGED NLINK NAME-NORMALIZED(aviso).
exit 0 = sin errores (avisos permitidos); 1 = algun error."""
import sys, os, json, argparse, collections, hashlib, unicodedata, stat
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q3lib import *

def sha256f(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''): h.update(b)
    return h.hexdigest()

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('vol'); ap.add_argument('root'); ap.add_argument('--scope'); ap.add_argument('--hash', action='store_true')
    ap.add_argument('--report'); ap.add_argument('--name-policy', default='exact', choices=['exact', 'nfd-equiv']); ap.add_argument('--skip-time', action='store_true')
    ap.add_argument('--skip-meta', action='store_true', help='solo existencia/tipo/contenido (sin uid/gid/modo/tiempos/hardlinks)')
    ap.add_argument('--allow-sidecars', action='store_true'); ap.add_argument('--ignore-file', help='rutas (o prefijos terminados en /) que se toleran como extra'); ap.add_argument('--time-res-s', action='store_true'); ap.add_argument('--allow-extra-nlink', action='store_true'); ap.add_argument('--quiet', action='store_true'); ap.add_argument('--max-print', type=int, default=8)
    a = ap.parse_args()
    man = load_manifest(a.vol); scope = read_scope(a.scope)
    if scope is not None:
        for p in list(scope): scope.update(ancestors(p))
    byp = {d['path']: d for d in man}
    sel = [d for d in man if scope is None or d['path'] in scope]
    res = collections.Counter(); rep = []; shown = collections.Counter()
    def emit(path, cls, detail=''):
        res[cls] += 1; rep.append(dict(path=path, result=cls, detail=detail))
        if not a.quiet and cls != 'OK' and shown[cls] < a.max_print: shown[cls] += 1; print('%-16s %s %s' % (cls, path, detail))
    # recorrido del arbol
    tree = set(); ttype = {}
    def walk(dirp, rel):
        with os.scandir(dirp) as it:
            for e in it:       # d_type de readdir: NO lo falsea fakeroot (lstat si; el modo falseado puede arrastrar un tipo obsoleto si se reutiliza un inodo)
                r = e.name if not rel else rel + '/' + e.name
                tree.add(r)
                if e.is_symlink(): ttype[r] = 'lnk'
                elif e.is_dir(follow_symlinks=False): ttype[r] = 'dir'; walk(e.path, r)
                elif e.is_file(follow_symlinks=False): ttype[r] = 'reg'
                else: ttype[r] = 'other'
    walk(a.root, '')
    norm_missing = {}
    if a.name_policy == 'nfd-equiv':
        mp = {unicodedata.normalize('NFD', p): p for p in byp}
    present_alias = {}
    ign = [l.rstrip('\n') for l in open(a.ignore_file, encoding='utf-8', errors='surrogateescape') if l.strip()] if a.ignore_file else []
    ign_exact = {x for x in ign if not x.endswith('/')}; ign_pre = [x for x in ign if x.endswith('/')]
    extras = sorted(p for p in tree if p not in byp and p not in ign_exact and not any((p + '/').startswith(x) for x in ign_pre))
    for p in extras:
        base = p.split(':com.apple.')[0] if is_sidecar(p) else None
        if base is not None and (base in byp or base in tree):
            emit(p, 'OK' if a.allow_sidecars else 'SIDECAR', 'xattr de 7z'); 
            if a.allow_sidecars: res['OK'] -= 1; res['sidecar_tolerado'] += 1
            continue
        if a.name_policy == 'nfd-equiv' and unicodedata.normalize('NFD', p) in mp and mp[unicodedata.normalize('NFD', p)] not in tree:
            present_alias[mp[unicodedata.normalize('NFD', p)]] = p; emit(p, 'NAME-NORMALIZED', 'forma distinta de la del manifiesto: ' + mp[unicodedata.normalize('NFD', p)]); continue
        emit(p, 'EXTRA')
    all_dev = collections.defaultdict(set); ino_seen = collections.defaultdict(set); grp_names = collections.defaultdict(list)
    for d in sel:
        p = d['path']; rp = p if p in tree else present_alias.get(p)
        if rp is None: emit(p, 'MISSING'); continue
        fp = os.path.join(a.root, rp); st = os.lstat(fp); ok = True
        t = ttype[rp]
        if t != d['type']: emit(p, 'TYPE', '%s != %s' % (t, d['type'])); continue
        if t == 'lnk' and os.readlink(fp) != d['target']: emit(p, 'TARGET', '%r != %r' % (os.readlink(fp), d['target'])); ok = False
        if t == 'reg':
            if st.st_size != d['size']:
                emit(p, 'EMPTY' if st.st_size == 0 else 'SIZE-MISMATCH', 'tam %d esperado %d' % (st.st_size, d['size'])); ok = False
            elif a.hash and d.get('sha256'):
                try: hh = sha256f(fp)
                except OSError as e: hh = None; emit(p, 'UNREADABLE', str(e)[:60]); ok = False
                if hh is not None and hh != d['sha256']: emit(p, 'FAIL', 'sha256 distinto'); ok = False
        if not a.skip_meta:
            if st.st_uid != d['uid']: emit(p, 'UID', '%d != %d' % (st.st_uid, d['uid'])); ok = False
            if st.st_gid != d['gid']: emit(p, 'GID', '%d != %d' % (st.st_gid, d['gid'])); ok = False
            if t != 'lnk' and (st.st_mode & 0o7777) != (d['mode'] & 0o7777): emit(p, 'MODE', '%04o != %04o' % (st.st_mode & 0o7777, d['mode'] & 0o7777)); ok = False
            if not a.skip_time and d['mtime_ns'] is not None and (st.st_mtime_ns // 10**9 if a.time_res_s else st.st_mtime_ns) != (d['mtime_ns'] // 10**9 if a.time_res_s else d['mtime_ns']): emit(p, 'TIME', '%d != %d' % (st.st_mtime_ns, d['mtime_ns'])); ok = False
            if t == 'reg':
                all_dev[(st.st_dev, st.st_ino)].add(d['inode'])
                if d['nlink'] > 1: ino_seen[d['inode']].add((st.st_dev, st.st_ino)); grp_names[d['inode']].append((p, st.st_nlink))
        if ok: emit(p, 'OK')
    if not a.skip_meta:
        full = collections.Counter(d['inode'] for d in man if d['type'] == 'reg' and d['nlink'] > 1)
        devino = all_dev
        for ino, s in ino_seen.items():
            if len(s) > 1: emit('inode %d (%s ...)' % (ino, grp_names[ino][0][0]), 'HARDLINK-SPLIT', '%d inodos reales para %d nombres presentes' % (len(s), len(grp_names[ino])))
            elif len(grp_names[ino]) == full[ino]:
                nl = grp_names[ino][0][1]
                if (nl < full[ino]) if a.allow_extra_nlink else (nl != full[ino]): emit(grp_names[ino][0][0], 'NLINK', 'st_nlink %d != %d' % (nl, full[ino]))
        for x, inos in devino.items():
            if len(inos) > 1: emit('st_ino %d' % x[1], 'HARDLINK-MERGED', 'inodos distintos del manifiesto comparten inodo real: %s' % sorted(inos)[:4])
    summ = dict(summary=True, volumen=a.vol, raiz_relativa=os.path.basename(a.root.rstrip('/')), entradas_manifiesto_en_alcance=len(sel), tree_entries=len(tree), results=dict(res))
    errs = sum(v for k, v in res.items() if k not in ('OK', 'NAME-NORMALIZED', 'sidecar_tolerado'))
    summ['errores'] = errs
    if a.report:
        with open(a.report, 'w', encoding='utf-8', errors='surrogateescape') as f:
            for r in rep:
                if r['result'] != 'OK': f.write(json.dumps(r, ensure_ascii=False) + '\n')
            f.write(json.dumps(summ) + '\n')
    print(json.dumps(summ)); sys.exit(1 if errs else 0)
main()
