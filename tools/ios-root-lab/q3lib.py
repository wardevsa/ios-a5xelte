"""q3lib: utilidades comunes de T04-Q3 (solo laboratorio). Python 3 stdlib."""
import os, re, sys, json, datetime
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xnu_name_adapter
# D-0024: copia en el repositorio de los scripts del laboratorio T04-R; el laboratorio se indica por entorno (nada de rutas absolutas)
Q3 = os.environ.get('IOS_ROOT_LAB') or sys.exit('IOS_ROOT_LAB: ruta del directorio r3 del laboratorio (con out/ y work/)')
DMGDIR = os.environ.get('IOS_IPSW_DIR', '')
FIELDS = ('Path', 'Size', 'Packed Size', 'Mode', 'Modified', 'Created', 'Accessed', 'Metadata Changed', 'Added Time',
          'Method', 'iNode', 'Links', 'Symbolic Link', 'User ID', 'Group ID', 'Characteristics', 'BSD Flags', 'Parent iNode', 'Primary Name')
_T = re.compile(r'^(\d{4})-(\d\d)-(\d\d) (\d\d):(\d\d):(\d\d)\.(\d{9})$')

def parse_time_ns(s):
    """'2026-04-30 04:13:14.000000000' (UTC) -> ns desde 1970 (puede ser negativo); '' -> None"""
    m = _T.match(s)
    if not m: return None
    y, mo, d, H, M, S_, ns = map(int, m.groups())
    days = (datetime.date(y, mo, d) - datetime.date(1970, 1, 1)).days
    return ((days * 86400 + H * 3600 + M * 60 + S_) * 10**9) + ns

def parse_lst(path):
    """Parsea un listado `7z l -slt`. -> lista de dict (bytes decodificados utf-8 surrogateescape).
    Los nombres con '\\n' romperian el formato: se comprueba que #registros == #'Path ='."""
    raw = open(path, 'rb').read()
    i = raw.index(b'\n----------\n')
    body = raw[i + 12:]
    recs = []
    for bl in body.split(b'\n\n'):
        d = {}
        for ln in bl.split(b'\n'):
            k, s, v = ln.partition(b' = ')
            if s: d[k.decode()] = v.decode('utf-8', 'surrogateescape')
            elif ln.endswith(b' ='): d[ln[:-2].decode()] = ''
        if 'Path' in d: recs.append(d)
    n_path = body.count(b'\nPath = ') + (1 if body.startswith(b'Path = ') else 0)
    assert n_path == len(recs), (n_path, len(recs))
    return recs

def mode_from_str(s):
    """'-rwsr-xr-x' -> int mode completo (tipo+permisos+suid/sgid/sticky)"""
    t = {'-': 0o100000, 'd': 0o040000, 'l': 0o120000, 'c': 0o020000, 'b': 0o060000, 'p': 0o010000, 's': 0o140000}[s[0]]
    m = 0
    special = {2: 0o4000, 5: 0o2000, 8: 0o1000}
    for i, c in enumerate(s[1:10]):
        if c in 'rwxst': m |= 1 << (8 - i)          # r, w, x o s/t (x activo)
        if c in 'stST': m |= special[i]
    return t | m

def load_jsonl(p):
    with open(p, encoding='utf-8') as f:
        for ln in f:
            if ln.strip(): yield json.loads(ln)

def fmt_ns(ns):
    if ns is None: return None
    s, n = divmod(ns, 10**9)
    return '%s.%09d' % (datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=s), n) if -62135596800 < s < 253402300799 else str(ns)

import shlex
def shq(s):
    """cita una ruta para sh/bash: shlex.quote si es UTF-8 valido sin controles; si no, $'\\xNN' byte a byte"""
    b = s.encode('utf-8', 'surrogateescape')
    try:
        t = b.decode('utf-8')
        if all(ord(c) >= 0x20 and ord(c) != 0x7f for c in t): return shlex.quote(t)
    except UnicodeDecodeError:
        pass
    return "$'" + ''.join('\\x%02x' % c for c in b) + "'"

def load_manifest(vol):
    """EL ÚNICO PUNTO de traducción de nombres (D-0017/D-0020): el manifiesto devuelve las rutas en la forma que XNU espera y sin las excluidas."""
    return xnu_name_adapter.translate_manifest(list(load_jsonl(os.path.join(Q3, 'out', 'man_%s.jsonl' % vol))), xnu_name_adapter.load_exclusions())

def read_scope(p):
    if not p: return None
    return {ln.rstrip('\n') for ln in open(p, encoding='utf-8', errors='surrogateescape') if ln.strip()}

def ancestors(p):
    out = []
    while '/' in p:
        p = p.rpartition('/')[0]; out.append(p)
    return out

def is_sidecar(name):
    return ':com.apple.' in name
