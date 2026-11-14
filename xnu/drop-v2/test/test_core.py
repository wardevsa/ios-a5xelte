#!/usr/bin/env python3
"""Pruebas del núcleo DROP v2 (herolte_drop_core.c): el C real, ejecutado por ctypes sobre un
sistema de ficheros en memoria con cortes de alimentación (fsmodel.py).

  python3 -I xnu/drop-v2/test/test_core.py [--quick]

Compila el núcleo con gcc en un directorio temporal (o usa HDC_LIB=/ruta/libhdc.so).
Con ASan: LD_PRELOAD=$(gcc -print-file-name=libasan.so) ASAN_OPTIONS=detect_leaks=0 HDC_LIB=... python3 ...
No toca el repositorio ni ningún dispositivo.
"""
import collections
import copy
import ctypes as C
import hashlib
import os
import random
import struct
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from fsmodel import FS, Crash, BarrierFail, TORN   # noqa: E402

BLOCK, CHUNK, LIST_MAX = 4096, 1 << 20, 65536
ROOT = '/private/var/herolte'
D = ROOT + '/.drop'
EIO, ENOENT, ENOSPC = 5, 2, 28
QUICK = '--quick' in sys.argv


# ----------------------------------------------------------------------------- biblioteca
def load_lib():
    path = os.environ.get('HDC_LIB')
    if not path:
        path = os.path.join(tempfile.mkdtemp(prefix='hdc-'), 'libhdc.so')
        subprocess.check_call(['gcc', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                               '-fsanitize=undefined', '-fno-sanitize-recover=undefined', '-DHDC_EXPOSE',
                               '-shared', '-fPIC', os.path.join(HERE, '..', 'herolte_drop_core.c'),
                               '-o', path])
    lib = C.CDLL(path)
    lib.hdc_boot.restype = C.c_int
    lib.hdc_boot.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p]
    lib.hdc_rd_init.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint64]
    for fn in (lib.hdc_at_off, lib.hdc_at_off_0333):
        fn.restype = C.c_int64
        fn.argtypes = [C.c_void_p, C.c_uint64, C.c_uint32]
    lib.hdc_sha256_buf.argtypes = [C.c_void_p, C.c_size_t, C.c_void_p]
    return lib


lib = load_lib()

ZR = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_uint64, C.c_void_p, C.c_uint32)
MK = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_char_p)
OW = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_char_p, C.c_uint32, C.POINTER(C.c_void_p))
WR = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p, C.c_uint64, C.c_void_p, C.c_uint32)
CW = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_void_p)
RD = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_char_p, C.c_void_p, C.c_uint32, C.POINTER(C.c_uint32))
RN = C.CFUNCTYPE(C.c_int, C.c_void_p, C.c_char_p, C.c_char_p)
BA = C.CFUNCTYPE(C.c_int, C.c_void_p)
LG = C.CFUNCTYPE(None, C.c_void_p, C.c_char_p)


class Ops(C.Structure):
    _fields_ = [('ctx', C.c_void_p), ('zone_read', ZR), ('fs_mkdir', MK), ('fs_exists', MK),
                ('fs_open_w', OW), ('fs_write', WR), ('fs_close_w', CW), ('fs_read', RD),
                ('fs_rename', RN), ('fs_unlink', MK), ('barrier', BA), ('log', LG)]


class Env:
    """Entorno de un arranque: zona + sistema de ficheros en memoria + inyección de fallos."""

    def __init__(s, fs, zone, fail=None, zone_fail_p=0.0, seed=0, fail_stage=0):
        s.fs, s.zone, s.crashed = fs, zone or b'', False
        s.handles, s.nh, s.logs = {}, 0, []
        s.fail = dict(fail or {})
        s.fail_stage = fail_stage       # errno para toda apertura dentro de .drop/stage/
        s.zone_fail_p, s.rng = zone_fail_p, random.Random(seed)
        s.ops = Ops(None, ZR(s.g(s.zone_read)), MK(s.g(s.mkdir)), MK(s.g(s.exists)), OW(s.g(s.open_w)),
                    WR(s.g(s.write)), CW(s.g(s.close_w)), RD(s.g(s.read)), RN(s.g(s.rename)),
                    MK(s.g(s.unlink)), BA(s.g(s.barrier)), LG(s.log))

    def g(s, fn):                       # guarda: tras un corte, toda operación falla sin efecto
        name = fn.__name__

        def w(*a):
            if s.crashed:
                return EIO
            if name in s.fail:
                return s.fail[name]
            try:
                return fn(*a)
            except Crash:
                s.crashed = True
                return EIO
            except BarrierFail:
                return EIO
            except OSError as e:
                return e.errno
        return w

    def zone_read(s, ctx, off, dst, n):
        if s.zone_fail_p and s.rng.random() < s.zone_fail_p:
            return EIO
        data = s.zone[off:off + n]
        C.memmove(dst, data + bytes(n - len(data)), n)
        return 0

    def mkdir(s, ctx, p):
        s.fs.mkdir_p(p.decode())
        return 0

    def exists(s, ctx, p):
        return 1 if s.fs.exists(p.decode()) else 0

    def open_w(s, ctx, p, mode, h):
        assert mode in (0o644, 0o755), mode
        if s.fail_stage and '/.drop/stage/' in p.decode():
            return s.fail_stage
        s.fs.write_new(p.decode(), b'')
        s.nh += 1
        s.handles[s.nh] = [p.decode(), bytearray()]
        h[0] = s.nh
        return 0

    def write(s, ctx, h, off, data, n):
        buf = s.handles[int(h)][1]
        assert off == len(buf), (off, len(buf))
        buf += C.string_at(data, n)
        return 0

    def close_w(s, ctx, h):
        p, buf = s.handles.pop(int(h))
        s.fs.set_data(p, bytes(buf))
        return 0

    def read(s, ctx, p, dst, cap, outlen):
        data = s.fs.read(p.decode())
        if data is None:
            return ENOENT
        data = data[:cap]
        C.memmove(dst, data, len(data))
        outlen[0] = len(data)
        return 0

    def rename(s, ctx, a, b):
        s.fs.rename(a.decode(), b.decode())
        return 0

    def unlink(s, ctx, p):
        s.fs.unlink(p.decode())
        return 0

    def barrier(s, ctx):
        s.fs.barrier()
        return 0

    def log(s, ctx, msg):
        s.logs.append(msg.decode())


WIN = C.create_string_buffer(CHUNK)
LST = C.create_string_buffer(LIST_MAX)


def boot(env):
    return lib.hdc_boot(C.byref(env.ops), WIN, LST)


# ----------------------------------------------------------------------------- zona (formato del host v2)
def pack_entries(files):
    entries, dirs = [], set()
    for rel, data, mode in files:
        parts = rel.split('/')
        for i in range(1, len(parts)):
            d = '/'.join(parts[:i])
            if d not in dirs:
                dirs.add(d)
                entries.append((ROOT + '/' + d, 0, b''))
        entries.append((ROOT + '/' + rel, mode, data))
    return entries


def raw_payload(entries):
    payload = bytearray()
    for path, mode, data in entries:
        pb = path if isinstance(path, bytes) else path.encode()
        payload += struct.pack('<IIQ', len(pb), mode, len(data)) + pb
        payload += b'\0' * (-len(payload) % 8)
        payload += data
        payload += b'\0' * (-len(payload) % 8)
    return bytes(payload)


def raw_zone(payload, count, gen, magic=b'HERODRP2', header_flip=None):
    hdr = bytearray(BLOCK)
    hdr[0:8] = magic
    struct.pack_into('<IIQQ', hdr, 8, 2, count, len(payload), gen)
    hdr[32:64] = hashlib.sha256(payload).digest()
    hdr[4064:] = hashlib.sha256(bytes(hdr[:4064])).digest()
    if header_flip is not None:
        hdr[header_flip] ^= 1
    return bytes(hdr) + payload


def build_zone(files, gen):
    entries = pack_entries(files)
    return raw_zone(raw_payload(entries), len(entries), gen)


GEN = 2
OLD = {'autorun': b'A1', 'wifi/nvram.txt': b'N1', 'wifi/fw.bin': b'F1',
       'apps/X.app/Info.plist': b'P1', 'apps/X.app/X': b'B1'}
NEWF = [('autorun', b'A2', 0o755), ('wifi/nvram.txt', b'N2', 0o644), ('wifi/fw.bin', b'F2', 0o644),
        ('apps/X.app/Info.plist', b'P2', 0o644), ('apps/X.app/X', b'B2', 0o755)]
ZONE = build_zone(NEWF, GEN)
SHA = ZONE[32:64]
TOKEN = f'{GEN}|{SHA.hex()}'.encode()
EXPECT = {ROOT + '/' + r: d for r, d, _ in NEWF}
OLDX = {ROOT + '/' + r: d for r, d in OLD.items()}


def initial():
    f = FS()
    for d in ('/private', '/private/var', ROOT):
        f.dirs.add(d)
    for rel, data in OLD.items():
        f.write_new(ROOT + '/' + rel, data)
    f.barrier()
    f.ops, f.nbar = 0, 0
    return f


def parse_state(b):
    if b in (None, TORN) or len(b) != 88 or b[:8] != b'HDROPST2':
        return None
    if hashlib.sha256(b[:56]).digest() != b[56:88]:
        return None
    phase, att, gen = struct.unpack_from('<IIQ', b, 8)
    return {'phase': phase, 'att': att, 'gen': gen, 'sha': b[24:56]}


def dest_ok(f, exp):
    return all(f.read(p) == d for p, d in exp.items())


def safety(img):
    v = []
    if any(img.read(p) == TORN for p in EXPECT):
        v.append('S3 destino TORN')
    st = parse_state(img.read(D + '/state'))
    if st and st['phase'] == 3 and st['gen'] == GEN and not dest_ok(img, EXPECT):
        v.append('S1 COMMITTED con destinos incorrectos')
    if img.read(D + '/ready') == TOKEN and not (st and st['phase'] == 3 and st['gen'] == GEN):
        v.append('S2 ready sin COMMITTED')
    return v


# ----------------------------------------------------------------------------- resultados
RESULTS = []


def check(name, ok, detail=''):
    RESULTS.append((name, ok, detail))
    print(f'  [{"OK" if ok else "FALLA"}] {name}{(" — " + detail) if detail and not ok else ""}')


def section(t):
    print(f'\n{t}')


# ----------------------------------------------------------------------------- pruebas
def test_sha():
    section('SHA-256 propio frente a hashlib')
    rng, bad = random.Random(1), 0
    out = C.create_string_buffer(32)
    for n in list(range(0, 200)) + [4063, 4064, 4096, 100000]:
        data = rng.randbytes(n)
        lib.hdc_sha256_buf(data, n, out)
        bad += out.raw != hashlib.sha256(data).digest()
    check('202 longitudes (incluye fronteras de bloque de 55/56/64 B)', bad == 0, f'{bad} distintas')


def reader_fuzz(fn, seed):
    rng = random.Random(seed)
    payload = rng.randbytes(3 * CHUNK + 12345)
    zone = bytes(BLOCK) + payload
    env = Env(None, zone, zone_fail_p=0.2, seed=seed)
    buf = C.create_string_buffer(CHUNK)
    rd = C.create_string_buffer(64)
    lib.hdc_rd_init(rd, C.byref(env.ops), buf, len(payload))
    bad, nulls, hits = collections.Counter(), 0, 0
    for _ in range(3000):
        mode = rng.random()
        off = rng.randrange(len(payload)) if mode < 0.5 else rng.choice(
            [0, CHUNK - 8, CHUNK, 2 * CHUNK - 1, len(payload) - 4, len(payload) - 1]) + rng.randrange(-3, 4)
        off = max(0, off)
        ln = rng.choice([1, 8, 16, 255, 4096, rng.randrange(1, CHUNK // 2)])
        r = fn(rd, off, ln)
        if r < 0:
            nulls += 1
            continue
        hits += 1
        if r + ln > CHUNK:
            bad['fuera de la ventana'] += 1
        elif buf.raw[r:r + ln] != payload[off:off + ln]:
            bad['contenido distinto del pedido'] += 1
    return bad, nulls, hits


def test_reader():
    section('Lector de payload: fallo de 0333 frente a la versión corregida (fuzz con lecturas fallidas)')
    tot_fixed, tot_0333 = collections.Counter(), collections.Counter()
    for seed in range(8 if QUICK else 30):
        b, _, _ = reader_fuzz(lib.hdc_at_off, seed)
        tot_fixed.update(b)
        b, _, _ = reader_fuzz(lib.hdc_at_off_0333, seed)
        tot_0333.update(b)
    check('versión corregida: 0 violaciones', not tot_fixed, str(dict(tot_fixed)))
    check('expresión de 0333: el fuzz reproduce el defecto', bool(tot_0333), 'no se reprodujo')
    print(f'      (0333 -> {dict(tot_0333)}; corregida -> {dict(tot_fixed)})')


def mal(entries_fn, count=None, extra=b'', gen=7):
    entries = entries_fn()
    payload = raw_payload(entries) + extra
    return raw_zone(payload, len(entries) if count is None else count, gen)


def test_rejects():
    section('Validación: paquetes inválidos no escriben nada')
    P = ROOT + '/'
    good = (P + 'autorun', 0o755, b'x')
    cases = {
        'cabecera v1': raw_zone(b'\0' * 8, 1, 7, magic=b'HERODRP1'),
        'cabecera con un bit cambiado': raw_zone(raw_payload([good]), 1, 7, header_flip=40),
        'ruta con ..': mal(lambda: [(P + '../x', 0o644, b'x')]),
        'componente .drop': mal(lambda: [(P + '.drop/state', 0o644, b'x')]),
        'componente .dropbox (reservado por prefijo)': mal(lambda: [(P + '.drop-id', 0o644, b'x')]),
        'modo setuid': mal(lambda: [(P + 'a', 0o4755, b'x')]),
        'modo 0600': mal(lambda: [(P + 'a', 0o600, b'x')]),
        'directorio con tamaño': mal(lambda: [(P + 'd', 0, b'xx')]),
        'fuera del prefijo': mal(lambda: [('/private/var/other/a', 0o644, b'x')]),
        'barra invertida': mal(lambda: [(P + 'a\\b', 0o644, b'x')]),
        'componente vacío a//b': mal(lambda: [(P + 'a//b', 0o644, b'x')]),
        'ruta con barra final': mal(lambda: [(P + 'a/', 0o644, b'x')]),
        'NUL dentro de la ruta': mal(lambda: [(P.encode() + b'a\0b', 0o644, b'x')]),
        'count mayor que las entradas': mal(lambda: [good], count=2),
        'count menor que las entradas': mal(lambda: [good, (P + 'b', 0o644, b'y')], count=1),
        'bytes sobrantes tras la última entrada': mal(lambda: [good], extra=b'\0' * 8),
    }
    # tamaño declarado mayor que el payload (hay que fabricar la cabecera a mano)
    e = raw_payload([good])
    cases['size mayor que el payload'] = raw_zone(
        e[:8] + struct.pack('<Q', 1 << 40) + e[16:], 1, 7)
    for name, zone in cases.items():
        f = initial()
        before = sorted(f.ns)
        env = Env(f, zone)
        rc = boot(env)
        ok = (rc == 0 and sorted(f.ns) == before and f.read(D + '/state') is None
              and f.read(D + '/ready') is None and dest_ok(f, OLDX))
        check(name, ok, f'rc={rc} cambió={sorted(set(f.ns) ^ set(before))}')
    f = initial()
    zone = bytearray(ZONE)
    zone[BLOCK + 40] ^= 1
    rc = boot(Env(f, bytes(zone)))
    check('payload con un byte cambiado (SHA no coincide)', rc == 0 and f.read(D + '/state') is None
          and dest_ok(f, OLDX))
    f = initial()
    rc = boot(Env(f, b''))
    check('sin paquete: no hace nada', rc == 0 and f.read(D + '/state') is None and dest_ok(f, OLDX))


def test_install_and_idempotence():
    section('Instalación completa, reinicio idempotente y consumo por hero-run')
    f = initial()
    env = Env(f, ZONE)
    rc = boot(env)
    st = parse_state(f.read(D + '/state'))
    check('instala, estado COMMITTED y ready publicado',
          rc == 0 and dest_ok(f, EXPECT) and st and st['phase'] == 3 and f.read(D + '/ready') == TOKEN,
          '; '.join(env.logs))
    check('modos: el bundle quedó con los dos ficheros y sin stage.list', f.read(D + '/stage.list') is None)
    check('la versión anterior del bundle está en .drop/trash', f.exists(D + '/trash/X.app.2'))
    snap, ops0 = f.snapshot(), f.ops
    rc = boot(Env(f, ZONE))
    check('segundo arranque: cero operaciones sobre el volumen', rc == 0 and f.snapshot() == snap and f.ops == ops0)
    # hero-run: mueve las apps y registra consumed
    f.rename(ROOT + '/apps/X.app', '/Applications/X.app')
    f.write_new(D + '/consumed.tmp', TOKEN)
    f.barrier()
    f.rename(D + '/consumed.tmp', D + '/consumed')
    f.unlink(D + '/ready')                      # peor caso: ready desaparece tras el consumo
    snap, ops0 = f.snapshot(), f.ops
    rc = boot(Env(f, ZONE))
    check('tras consumed no se republica ready ni se reinstala', rc == 0 and f.snapshot() == snap and f.ops == ops0)


def test_big():
    section('Paquete grande (varias ventanas de 1 MiB, fichero de 1,7 MiB, fichero vacío)')
    rng = random.Random(5)
    files = [('lib/big.dylib', rng.randbytes(1_800_000), 0o755), ('lib/empty', b'', 0o644)]
    files += [(f'apps/Y.app/f{i}', rng.randbytes(300_000 + i), 0o644) for i in range(4)]
    zone = build_zone(files, 9)
    f = initial()
    env = Env(f, zone)
    rc = boot(env)
    ok = rc == 0 and all(f.read(ROOT + '/' + r) == d for r, d, _ in files)
    check('contenido idéntico byte a byte', ok, f'rc={rc} {env.logs}')
    f = initial()
    rc = boot(Env(f, zone, fail_stage=ENOSPC))
    check('ENOSPC al preparar: destinos intactos', rc == ENOSPC and dest_ok(f, OLDX))


def test_attempts():
    section('Reintentos: no hay bucle de reinstalación')
    f = initial()
    rcs = [boot(Env(f, ZONE, fail_stage=ENOSPC)) for _ in range(3)]
    st = parse_state(f.read(D + '/state'))
    check('3 intentos fallidos devuelven el error y cuentan', rcs == [ENOSPC] * 3 and st and st['phase'] == 1
          and st['att'] == 3, f'{rcs} {st}')
    env = Env(f, ZONE)
    rc = boot(env)
    st = parse_state(f.read(D + '/state'))
    check('el cuarto arranque abandona (FAILED) sin reescribir nada', rc == 0 and st and st['phase'] == 4
          and dest_ok(f, OLDX), '; '.join(env.logs))
    snap, ops0 = f.snapshot(), f.ops
    boot(Env(f, ZONE))
    check('FAILED es estable: sin operaciones', f.snapshot() == snap and f.ops == ops0)
    zone2 = build_zone(NEWF, GEN + 1)
    rc = boot(Env(f, zone2))
    check('una generación nueva se instala', rc == 0 and dest_ok(f, EXPECT))


def converge_checks(img, zone_after, res, first, key, seed_name):
    r = copy.deepcopy(img)
    r.ops, r.crash_at, r.fail_bar = 0, None, None
    env = Env(r, zone_after)
    rc = boot(env)
    if rc != 0:
        res['recuperación devuelve error'] += 1
        first.setdefault('rc', key)
        return
    if zone_after:
        if not dest_ok(r, EXPECT) or r.read(D + '/ready') != TOKEN:
            res['CONV no converge a la versión nueva'] += 1
            first.setdefault('CONV', key)
            return
        snap, ops0 = r.snapshot(), r.ops
        boot(Env(r, zone_after))
        if r.snapshot() != snap or r.ops != ops0:
            res['IDEM el segundo arranque escribe'] += 1
    else:
        kinds = {('new' if r.read(q) == EXPECT[q] else 'old' if r.read(q) == OLDX[q] else 'x') for q in EXPECT}
        if len(kinds) != 1 or 'x' in kinds:
            res['ATOM paquete mezclado o dañado (zona borrada)'] += 1
            first.setdefault('ATOM', key)


def crash_enumeration(fail_bar=None):
    dry = initial()
    dry.fail_bar = None
    boot(Env(dry, ZONE))
    total = dry.ops
    res, first = collections.Counter(), {}
    modes = ('torn', 'full', 1) if QUICK else ('torn', 'full', 1, 2, 3)
    for k in range(total + 1):
        f = initial()
        f.crash_at, f.fail_bar = k, fail_bar
        env = Env(f, ZONE)
        boot(env)
        if fail_bar and f.read(D + '/ready') == TOKEN and not env.crashed:
            st = parse_state(f.read(D + '/state'))
            if not (st and st['phase'] == 3):
                res['ready publicado tras fallo de barrera'] += 1
        for p in range(len(f.mlog) + 1):
            for za, mode in [(z, m) for z in (ZONE, None) for m in modes]:
                img = f.image(p, mode, f'{k}:{p}')
                res['imagenes'] += 1
                for v in safety(img):
                    res[v] += 1
                    first.setdefault(v, (k, p, mode))
                converge_checks(img, za, res, first, (k, p, mode, za is not None), '')
    return total, res, first


def test_crashes():
    section('Cortes de alimentación en cada operación (C real sobre el modelo)')
    total, res, first = crash_enumeration()
    bad = {k: v for k, v in res.items() if k != 'imagenes'}
    check(f'{res["imagenes"]} imágenes de corte ({total} operaciones): sin violaciones', not bad,
          f'{bad} primer caso: {first}')


def test_barrier_failures():
    section('Fallo del sync del dispositivo en cada barrera (ETIMEDOUT/EIO): se aborta sin publicar')
    dry = initial()
    boot(Env(dry, ZONE))
    nb = dry.nbar
    bad_all = {}
    for b in range(1, nb + 1):
        _, res, first = crash_enumeration(fail_bar=b)
        bad = {k: v for k, v in res.items() if k != 'imagenes'}
        if bad:
            bad_all[b] = (bad, first)
    check(f'{nb} barreras probadas, cada una fallando', not bad_all, str(bad_all))


def test_double_fault():
    section('Segundo corte durante la recuperación')
    dry = initial()
    boot(Env(dry, ZONE))
    total, n, bad = dry.ops, 0, collections.Counter()
    step = 3 if QUICK else 1
    for k in range(0, total + 1, step):
        f = initial()
        f.crash_at = k
        boot(Env(f, ZONE))
        for p in range(len(f.mlog) + 1):
            img = f.image(p, 'torn', f'{k}:{p}')
            probe = copy.deepcopy(img)
            probe.ops = 0
            probe.crash_at = None
            boot(Env(probe, ZONE))
            for j in range(0, probe.ops + 1, step):
                r = copy.deepcopy(img)
                r.ops, r.crash_at = 0, j
                boot(Env(r, ZONE))
                for p2 in range(len(r.mlog) + 1):
                    for mode in ('torn', 'full'):
                        r2 = r.image(p2, mode, f'd{j}:{p2}')
                        r2.ops = 0
                        n += 1
                        rc = boot(Env(r2, ZONE))
                        if rc != 0 or not dest_ok(r2, EXPECT) or r2.read(D + '/ready') != TOKEN:
                            bad['no converge'] += 1
    check(f'{n} casos de doble fallo', not bad, str(dict(bad)))


if __name__ == '__main__':
    test_sha()
    test_reader()
    test_rejects()
    test_install_and_idempotence()
    test_big()
    test_attempts()
    test_crashes()
    test_barrier_failures()
    test_double_fault()
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f'\n{len(RESULTS) - len(failed)}/{len(RESULTS)} comprobaciones correctas')
    sys.exit(1 if failed else 0)
