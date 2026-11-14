#!/usr/bin/env python3
"""Modelo ejecutable del protocolo DROP (no es el kernel): enumera cortes de alimentacion.

Supuestos del modelo (pesimistas, ver informe de persistencia):
  * Los metadatos (mkdir/create/rename/unlink) se persisten como un PREFIJO del orden emitido
    desde la ultima barrera (orden del journal).
  * Los datos de fichero NO estan en el journal: tras un corte, un inodo escrito despues de la
    ultima barrera puede aparecer con contenido TORN aunque su nombre haya persistido.
  * barrier() = F_FULLFSYNC + sync directo del dispositivo: lo anterior pasa a ser duradero.
  * Un fsync sin barrera NO prueba nada (A2 del informe).
"""
import collections
import copy
import hashlib
import random
import sys

TORN = '<TORN>'
H = '/herolte'
D = H + '/.drop'
ST = D + '/stage'
TR = D + '/trash'


class Crash(Exception):
    pass


class BarrierFail(Exception):
    pass


class Broken(Exception):
    pass


class FS:
    def __init__(s):
        s.dirs = {'/', H}
        s.ns = {}
        s.ino = {}
        s.nxt = 1
        s.base = (set(s.dirs), dict(s.ns))
        s.mlog = []
        s.ops = 0
        s.crash_at = None
        s.nbar = 0
        s.fail_bar = None

    def tick(s):
        if s.crash_at is not None and s.ops >= s.crash_at:
            raise Crash()
        s.ops += 1

    @staticmethod
    def parent(p):
        return p.rsplit('/', 1)[0] or '/'

    @staticmethod
    def _apply(op, dirs, ns):
        k = op[0]
        if k == 'mkdir':
            dirs.add(op[1])
        elif k == 'create':
            ns[op[1]] = op[2]
        elif k == 'unlink':
            ns.pop(op[1], None)
        elif k == 'rename':
            a, b = op[1], op[2]
            if a in dirs:
                moved = [q for q in dirs if q == a or q.startswith(a + '/')]
                for q in moved:
                    dirs.discard(q)
                    dirs.add(b + q[len(a):])
                for q in [q for q in ns if q.startswith(a + '/')]:
                    ns[b + q[len(a):]] = ns.pop(q)
            else:
                ns[b] = ns.pop(a)

    def do(s, op):
        s._apply(op, s.dirs, s.ns)
        s.mlog.append(op)

    def exists(s, p):
        return p in s.ns or p in s.dirs

    def read(s, p):
        i = s.ns.get(p)
        return None if i is None else s.ino[i]['v']

    def mkdir_p(s, p):
        cur = ''
        for x in p.strip('/').split('/'):
            cur += '/' + x
            if cur not in s.dirs:
                s.tick()
                s.do(('mkdir', cur))

    def write_new(s, p, data):
        s.mkdir_p(s.parent(p))
        if p in s.ns:                       # O_TRUNC en el sitio
            s.tick()
            i = s.ns[p]
            s.ino[i] = {'v': '', 'dur': False}
        else:
            s.tick()
            i = s.nxt
            s.nxt += 1
            s.ino[i] = {'v': '', 'dur': False}
            s.do(('create', p, i))
        s.tick()
        s.ino[i]['v'] = data
        s.ino[i]['dur'] = False

    def rename(s, a, b):
        s.mkdir_p(s.parent(b))
        if a in s.dirs and b in s.dirs:       # POSIX: solo sobre un directorio vacio
            assert not any(q.startswith(b + '/') for q in list(s.dirs) + list(s.ns)), 'ENOTEMPTY'
        s.tick()
        s.do(('rename', a, b))

    def unlink(s, p):
        s.tick()
        s.do(('unlink', p))

    def barrier(s):
        s.tick()
        s.nbar += 1
        if s.fail_bar == s.nbar:
            raise BarrierFail()
        s.base = (set(s.dirs), dict(s.ns))
        s.mlog = []
        for d in s.ino.values():
            d['dur'] = True

    def image(s, p, mode='torn', salt=''):
        dirs, ns = set(s.base[0]), dict(s.base[1])
        for op in s.mlog[:p]:
            s._apply(op, dirs, ns)
        n = FS()
        n.dirs, n.ns, n.nxt = dirs, ns, s.nxt
        for path, i in ns.items():
            d = s.ino[i]
            if d['dur'] or mode == 'full':
                keep = True
            elif mode == 'torn':
                keep = False
            else:                              # variante aleatoria reproducible por inodo
                keep = random.Random(f'{mode}:{salt}:{i}').random() < 0.5
            n.ino[i] = {'v': d['v'] if keep else TORN, 'dur': True}
        n.base = (set(dirs), dict(ns))
        return n

    def snapshot(s):
        return (sorted((p, s.read(p)) for p in s.ns), sorted(s.dirs))


def rec(phase, gen, sha):
    body = f'{phase}|{gen}|{sha}'
    return body + '|' + hashlib.sha256(body.encode()).hexdigest()[:8]


def parse_rec(x):
    if x in (None, TORN):
        return None
    try:
        body, chk = x.rsplit('|', 1)
        if hashlib.sha256(body.encode()).hexdigest()[:8] != chk:
            return None
        phase, gen, sha = body.split('|')
    except ValueError:
        return None
    return {'phase': phase, 'gen': gen, 'sha': sha}


class Zone:
    def __init__(s, gen, files):
        s.gen = gen
        s.files = files
        s.sha = hashlib.sha256(repr(files).encode()).hexdigest()[:16]
        s.token = f'{gen}|{s.sha}'

    def units(s):
        out, seen = [], set()
        for path, _ in s.files:
            parts = path.split('/')
            if parts[0] == 'apps' and len(parts) > 2:
                u = ('B', 'apps/' + parts[1])
            else:
                u = ('F', path)
            if u not in seen:
                seen.add(u)
                out.append(u)
        out.sort(key=lambda u: u[1] == 'wifi/fw.bin')      # fw.bin al final
        return out


NEW = Zone('2', [('autorun', 'A2'), ('wifi/nvram.txt', 'N2'), ('wifi/fw.bin', 'F2'),
                 ('apps/X.app/Info.plist', 'P2'), ('apps/X.app/X', 'B2')])
OLD = {'autorun': 'A1', 'wifi/nvram.txt': 'N1', 'wifi/fw.bin': 'F1',
       'apps/X.app/Info.plist': 'P1', 'apps/X.app/X': 'B1'}
EXPECT = {H + '/' + p: d for p, d in NEW.files}
OLDX = {H + '/' + p: d for p, d in OLD.items()}


def initial():
    f = FS()
    for p, d in OLD.items():
        f.write_new(H + '/' + p, d)
    f.barrier()
    f.ops = 0
    f.nbar = 0
    return f


# ------------------------------------------------------------------ protocolo v2
def put(f, path, data):                 # reemplazo atomico: tmp + rename
    f.write_new(path + '.tmp', data)
    f.barrier()                         # datos del tmp duraderos ANTES del rename (no van por el journal)
    f.rename(path + '.tmp', path)


def load_list(f, zone):
    t = f.read(D + '/stage.list')
    if t in (None, TORN):
        return None
    lines = t.split('\n')
    if lines[0] != zone_token(f):
        return None
    return [tuple(x.split(' ', 1)) for x in lines[1:] if x]


def zone_token(f):
    st = parse_rec(f.read(D + '/state'))
    return f"{st['gen']}|{st['sha']}" if st else None


def commit(f, units, gen):
    for kind, name in units:
        src, dst = ST + '/' + name, H + '/' + name
        if not f.exists(src):
            continue                    # ya hecho (idempotente)
        if kind == 'B' and f.exists(dst):
            f.rename(dst, TR + '/' + name.rsplit('/', 1)[1] + '.' + gen)   # nombre por generacion
        f.rename(src, dst)


def ensure_ready(f, token):
    if f.read(D + '/consumed') == token or f.read(D + '/ready') == token:
        return
    put(f, D + '/ready', token)


def finish(f, st):
    token = f"{st['gen']}|{st['sha']}"
    f.barrier()                         # B3: renames de commit duraderos
    put(f, D + '/state', rec('COMMITTED', st['gen'], st['sha']))
    f.barrier()                         # B4: COMMITTED duradero antes de publicar
    ensure_ready(f, token)
    for q in [q for q in f.ns if q.startswith(TR + '/')]:
        f.unlink(q)
    if f.exists(D + '/stage.list'):
        f.unlink(D + '/stage.list')


def boot_new(f, zone):
    f.mkdir_p(D)
    if f.exists(D + '/state.tmp'):
        f.unlink(D + '/state.tmp')
    st = parse_rec(f.read(D + '/state'))
    if st and st['phase'] == 'STAGED':
        units = load_list(f, zone)
        if units is None:
            raise Broken('STAGED sin stage.list valido')
        commit(f, units, st['gen'])
        finish(f, st)
        return
    if zone is None:
        return
    if st and st['phase'] == 'COMMITTED' and (st['gen'], st['sha']) == (zone.gen, zone.sha):
        ensure_ready(f, zone.token)
        return
    for path, data in zone.files:                       # staging
        f.write_new(ST + '/' + path, data)
    put(f, D + '/stage.list', zone.token + '\n' + '\n'.join(f'{k} {n}' for k, n in zone.units()))
    put(f, D + '/state', rec('STAGED', zone.gen, zone.sha))
    f.barrier()                                         # B2: STAGED duradero antes de tocar destinos
    st = parse_rec(f.read(D + '/state'))
    commit(f, load_list(f, zone), st['gen'])
    finish(f, st)


def consume(f):
    tok = f.read(D + '/ready')
    if tok in (None, TORN) or f.read(D + '/consumed') == tok:
        return
    for q in sorted(p for p in f.dirs if p.startswith(H + '/apps/') and p.endswith('.app')):
        f.rename(q, '/Applications/' + q.rsplit('/', 1)[1])
    put(f, D + '/consumed', tok)
    f.barrier()


# ------------------------------------------------------------ protocolo 0332/0333
def boot_old(f, zone):
    if zone is None:
        return
    ident = zone.token
    drop_id, ready = f.read(H + '/.drop-id'), f.read(H + '/apps/.ready')
    if drop_id == ident and ready == ident:
        return
    if drop_id == ident:
        f.write_new(H + '/apps/.ready', ident)
        return
    for path, data in zone.files:
        f.write_new(H + '/' + path, data)
    f.write_new(H + '/apps/.ready', ident)
    f.write_new(H + '/.drop-id', ident)


# ------------------------------------------------------------------ comprobaciones
def dest_ok(f, exp):
    return all(f.read(p) == d for p, d in exp.items())


def safety_new(img):
    v = []
    if any(img.read(p) == TORN for p in EXPECT):
        v.append('S3 destino TORN')
    st = parse_rec(img.read(D + '/state'))
    if st and st['phase'] == 'COMMITTED' and st['gen'] == NEW.gen and not dest_ok(img, EXPECT):
        v.append('S1 COMMITTED con destinos incorrectos')
    if img.read(D + '/ready') == NEW.token and not (st and st['phase'] == 'COMMITTED'):
        v.append('S2 ready sin COMMITTED')
    return v


def safety_old(img):
    v = []
    if any(img.read(p) == TORN for p in EXPECT):
        v.append('S3 destino TORN')
    if img.read(H + '/.drop-id') == NEW.token and not dest_ok(img, EXPECT):
        v.append('S1 .drop-id con destinos incorrectos')
    return v


def run(proto, fail_bar=None):
    boot, safety = (boot_new, safety_new) if proto == 'new' else (boot_old, safety_old)
    dry = initial()
    boot(dry, NEW)
    total = dry.ops
    res = collections.Counter()
    first = {}
    for k in range(total + 1):
        f = initial()
        f.crash_at = k
        f.fail_bar = fail_bar
        try:
            boot(f, NEW)
        except (Crash, BarrierFail):
            pass
        if fail_bar and f.read(D + '/ready') == NEW.token and not parse_rec(f.read(D + '/state')):
            res['ready sin estado tras BarrierFail'] += 1
        for p in range(len(f.mlog) + 1):
            for zone_after, mode in [(z, m) for z in (NEW, None) for m in ('torn', 'full', 1, 2, 3)]:
                img = f.image(p, mode, f'{k}:{p}')
                res['imagenes'] += 1
                for viol in safety(img):
                    res[viol] += 1
                    first.setdefault(viol, (k, p, zone_after is not None))
                r = copy.deepcopy(img)
                r.ops = 0
                try:
                    boot(r, zone_after)
                except Broken:
                    res['Broken (STAGED irrecuperable)'] += 1
                    continue
                if zone_after is not None:
                    if not dest_ok(r, EXPECT):
                        res['CONV no converge a la version nueva'] += 1
                        first.setdefault('CONV', (k, p, True))
                        continue
                    if proto == 'new':
                        snap, ops0 = r.snapshot(), r.ops
                        boot(r, zone_after)
                        if r.snapshot() != snap or r.ops != ops0:
                            res['IDEM segundo arranque escribe'] += 1
                else:
                    kinds = {('new' if r.read(q) == EXPECT[q] else 'old' if r.read(q) == OLDX[q] else 'x')
                             for q in EXPECT}
                    if len(kinds) != 1 or 'x' in kinds:
                        res['ATOM paquete mezclado/dañado (zona borrada)'] += 1
                        first.setdefault('ATOM', (k, p, False))
    return total, res, first


def double_fault():
    bad, n = collections.Counter(), 0
    dry = initial()
    boot_new(dry, NEW)
    for k in range(dry.ops + 1):
        f = initial()
        f.crash_at = k
        try:
            boot_new(f, NEW)
        except (Crash, BarrierFail):
            pass
        for p in range(len(f.mlog) + 1):
            img = f.image(p, 'torn', f'{k}:{p}')
            probe = copy.deepcopy(img)
            probe.ops = 0
            try:
                boot_new(probe, NEW)
            except Broken:
                bad['Broken'] += 1
                continue
            for j in range(probe.ops + 1):
                r = copy.deepcopy(img)
                r.ops = 0
                r.crash_at = j
                try:
                    boot_new(r, NEW)
                except Crash:
                    pass
                for p2 in range(len(r.mlog) + 1):
                    for mode in ('torn', 'full'):
                        r2 = r.image(p2, mode, f'd{j}:{p2}')
                        r2.ops = 0
                        n += 1
                        try:
                            boot_new(r2, NEW)
                        except Broken:
                            bad['Broken'] += 1
                            continue
                        if not dest_ok(r2, EXPECT):
                            bad['no converge'] += 1
    return f'{n} casos, violaciones={dict(bad) or "ninguna"}'


def test_consume():
    f = initial()
    boot_new(f, NEW)
    consume(f)
    snap = f.snapshot()
    boot_new(f, NEW)
    ok1 = f.snapshot() == snap and f.read(D + '/ready') == NEW.token
    consume(f)
    ok2 = f.snapshot() == snap
    return ok1 and ok2 and f.exists('/Applications/X.app') and not f.exists(H + '/apps/X.app')


if __name__ == '__main__':
    print('Supuestos: prefijo de metadatos, datos no journaled, barrier = unica garantia de durabilidad.\n')
    for proto, title in (('old', 'PROTOCOLO 0332/0333 (sin barreras, escritura en el sitio)'),
                         ('new', 'PROTOCOLO v2 (staging + barreras + estado atomico)')):
        total, res, first = run(proto)
        print(title)
        print(f'  operaciones por instalacion: {total}')
        for key in sorted(res):
            print(f'  {key}: {res[key]}')
        if first:
            print('  primer caso (corte tras op, prefijo, zona presente):', first)
        print()
    print('v2 con fallo del sync de dispositivo en cada barrera (la instalacion aborta, sin publicar):')
    dry = initial()
    boot_new(dry, NEW)
    for b in range(1, dry.nbar + 1):
        total, res, first = run('new', fail_bar=b)
        bad = {k: v for k, v in res.items() if k != 'imagenes'}
        print(f'  barrera {b}: imagenes={res["imagenes"]} violaciones={bad or "ninguna"}')
    print('\nv2 doble fallo (segundo corte durante la recuperacion):', double_fault())
    print('\nv2 consumo por hero-run + rearranque idempotente:', 'OK' if test_consume() else 'FALLA')
