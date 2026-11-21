#!/usr/bin/env python3
"""apply_meta.py VOL ROOT --mode dry-run|apply [--scope F] [--emit SCRIPT]
Aplica el manifiesto de metadatos a un arbol de LABORATORIO.  Fases (orden fijo):
  1 mkdir -p de todos los directorios del manifiesto (incluye directorios vacios)
  2 symlinks (ln -sfn destino ruta)
  3 hardlinks (ln -f canonico nombre)  [misma logica que relink.py]
  4 chown -h uid:gid  (antes de chmod: chown limpia setuid/setgid)
  5 chmod 07777 (no se aplica a symlinks: Linux no tiene lchmod; su modo 0755 de APFS queda solo en el manifiesto)
  6 mtime (touch -h -m -d @s.ns; ficheros/symlinks primero, directorios del mas profundo al mas superficial)
  7 bsd_flags: NO se aplican (UF_COMPRESSED 0x20 seria incorrecto: el contenido ya esta descomprimido); se listan como comentario.
dry-run : no toca el arbol; escribe el script de comandos que ejecutaria root (cd "$ROOT"; set -eu).
apply   : SOLO dentro de fakeroot (exige FAKEROOTKEY); ejecuta las mismas operaciones con os.*; nunca privilegios reales."""
import sys, os, json, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from q3lib import *
import relink
import guard

def build(man, scope):
    sel = [d for d in man if scope is None or d['path'] in scope]
    return sel

def tsarg(ns, res=False):
    s, n = divmod(ns, 10**9); return '@%d.%09d' % (s, 0 if res else n)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('vol'); ap.add_argument('root'); ap.add_argument('--mode', required=True, choices=['dry-run', 'apply'])
    ap.add_argument('--scope'); ap.add_argument('--emit'); ap.add_argument('--report')
    ap.add_argument('--mount-point'); ap.add_argument('--image'); ap.add_argument('--test-fakeroot', action='store_true'); ap.add_argument('--time-res-s', action='store_true', help='mtime truncado a segundos (HFS+)'); a = ap.parse_args()
    man = load_manifest(a.vol); scope = read_scope(a.scope)
    if scope is not None:
        for p in list(scope): scope.update(ancestors(p))        # los ancestros tambien reciben metadatos
    sel = build(man, scope)
    dirs = sorted([d for d in sel if d['type'] == 'dir'], key=lambda d: d['path'].count('/'))
    lnks = [d for d in sel if d['type'] == 'lnk']; files = [d for d in sel if d['type'] == 'reg']
    allm = [d for d in sel]
    cmds = ['# apply_meta.py vol=%s: %d entradas (%d dir, %d reg, %d lnk).  Ejecutar como ROOT=dir; cd "$ROOT"' % (a.vol, len(sel), len(dirs), len(files), len(lnks)), 'set -eu']
    st = collections.Counter(); apply = a.mode == 'apply'
    if apply:
        if not a.test_fakeroot and not (a.mount_point and a.image): sys.exit('apply real exige --mount-point y --image (imagen de laboratorio)')
        guard.assert_lab_mount(a.mount_point or a.root, a.image or '', test_fakeroot=a.test_fakeroot)
        if a.mount_point: guard.assert_under(a.root, a.mount_point)
    os.chdir(a.root) if apply else None
    R = lambda p: p
    # 1 directorios
    cmds.append('# fase 1: directorios')
    for d in dirs:
        cmds.append('mkdir -p -- %s' % shq(d['path']))
        if apply: os.makedirs(d['path'], exist_ok=True)
        st['dirs'] += 1
    # 2 symlinks
    cmds.append('# fase 2: symlinks')
    for d in lnks:
        cmds.append('ln -sfn -- %s %s' % (shq(d['target']), shq(d['path'])))
        if apply:
            os.makedirs(os.path.dirname(d['path']) or '.', exist_ok=True)
            if os.path.lexists(d['path']): os.remove(d['path'])
            os.symlink(d['target'], d['path'])
        st['symlinks'] += 1
    # 3 hardlinks
    cmds.append('# fase 3: hardlinks')
    hc = relink.plan(man, scope); cmds += hc
    rep, bad = {}, []
    if apply: rep, _, bad = relink.run(man, '.', scope, dry=False)
    else: rep = {'enlaces_a_crear': len(hc)}
    st['hardlinks_nombres_enlazados'] = rep.get('enlaces_a_crear', 0); st['hardlink_divergentes'] = len(bad)
    # 4 chown
    cmds.append('# fase 4: propietario (chown -h)')
    for d in allm:
        cmds.append('chown -h %d:%d -- %s' % (d['uid'], d['gid'], shq(d['path'])))
        if apply and os.path.lexists(d['path']): os.chown(d['path'], d['uid'], d['gid'], follow_symlinks=False)
        st['chown'] += 1
    # 5 chmod
    cmds.append('# fase 5: modo (chmod; symlinks omitidos)')
    for d in files + sorted(dirs, key=lambda d: -d['path'].count('/')):
        cmds.append('chmod %04o -- %s' % (d['mode'] & 0o7777, shq(d['path'])))
        if apply and os.path.lexists(d['path']): os.chmod(d['path'], d['mode'] & 0o7777)
        st['chmod'] += 1
        if d['mode'] & 0o6000: st['chmod_setuid_setgid'] += 1
    # 6 mtime
    cmds.append('# fase 6: mtime (ns)')
    for d in files + lnks + sorted(dirs, key=lambda d: -d['path'].count('/')):
        if d['mtime_ns'] is None: continue
        cmds.append('touch -h -m -d %s -- %s' % (tsarg(d['mtime_ns'], a.time_res_s), shq(d['path'])))
        if apply and os.path.lexists(d['path']):
            mt = d['mtime_ns'] - (d['mtime_ns'] % 10**9 if a.time_res_s else 0); at = (d['atime_ns'] if d['atime_ns'] is not None else d['mtime_ns']); at -= (at % 10**9 if a.time_res_s else 0)
            os.utime(d['path'], ns=(at, mt), follow_symlinks=False)
        st['mtime'] += 1
    cmds.append('# fase 7: chflags NO aplicados')
    fl = collections.Counter(d['bsd_flags'] for d in allm)
    for k, v in sorted(fl.items()): cmds.append('# bsd_flags=0x%x: %d entradas (%s)' % (k, v, 'UF_COMPRESSED: NO se copia (imagen sin comprimir)' if k == 0x20 else 'ninguno' if k == 0 else 'REVISAR'))
    st['bsd_flags_distintos_de_0_y_0x20'] = sum(v for k, v in fl.items() if k not in (0, 0x20))
    if a.emit: open(a.emit, 'w', encoding='utf-8', errors='surrogateescape').write('\n'.join(cmds) + '\n')
    st['comandos_emitidos'] = sum(1 for c in cmds if not c.startswith('#') and c != 'set -eu')
    print(json.dumps(dict(st)))
    if a.report: json.dump(dict(st), open(a.report, 'w'), indent=1)
main()
