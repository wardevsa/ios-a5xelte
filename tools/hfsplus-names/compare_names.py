#!/usr/bin/env python3
"""Three-level comparison of how a name is stored on HFS+: XNU (its own utf8_decodestr), Linux hfsplus (its own decompose table) and the lab image.
READ-ONLY on the inputs; writes only into --out, which must not exist. Everything is compared on UTF-16 units / code points, never on the value of
single bytes of the UTF-16 form (U+0301 is the bytes 03 01, both below 0x80).

  compare_names.py --catalog catalog.jsonl --manifests DIR(man_{os,systemos,appos}.jsonl) --xnu-harness xnu_nfd --xnu-src DIR(with xnu/bsd/vfs/*)
                   --ko hfsplus.ko[.zst] --kernel kernel.development.herolte --out NEWDIR

NEWDIR: checks.tsv (every check, PASS/FAIL), results.json, inputs.sha256 (inputs AND the scripts that produced the result), tables_vs_kernel.tsv,
        names329.tsv, diff_names.tsv (input/Linux/XNU units of each differing name), diff_chars_in_names.tsv, bmp_diff_chars.tsv, summary.txt.
Exit status 0 only when EVERY check passed. No equivalence between the two implementations is claimed by this script: it reports where they differ.
The tsv files contain Apple's file names: keep them out of git."""
import argparse, collections, hashlib, json, os, re, struct, subprocess, sys, unicodedata
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import hfs_names as H

ap = argparse.ArgumentParser()
for k in ('catalog', 'manifests', 'xnu-harness', 'xnu-src', 'ko', 'kernel', 'out'): ap.add_argument('--' + k, required=True)
a = ap.parse_args()
os.makedirs(a.out)                                                     # refuses to reuse an existing directory
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
hx = lambda u: ' '.join('%04X' % x for x in u)
CHECKS = []
def check(name, ok, detail=''): CHECKS.append((name, bool(ok), detail)); return ok
def run_harness(strings):
    p = subprocess.run([a.xnu_harness], input='\n'.join(strings) + '\n', capture_output=True, text=True, check=True)
    out = []
    for line in p.stdout.splitlines():
        f = line.split(); out.append(None if f[0] != '0' else [int(x, 16) for x in f[1:]])
    return out

# ---------------------------------------------------------------------------------------------------------------- tables of XNU vs the kernel
elf = subprocess.run(['readelf', '-SW', a.xnu_harness], capture_output=True, text=True, check=True).stdout
m = re.search(r'\.rodata\s+PROGBITS\s+([0-9a-f]+)\s+([0-9a-f]+)', elf); ro_addr, ro_off = int(m.group(1), 16), int(m.group(2), 16)
harness = open(a.xnu_harness, 'rb').read(); kernel = open(a.kernel, 'rb').read()
syms = {}
for line in subprocess.run(['nm', '-S', a.xnu_harness], capture_output=True, text=True, check=True).stdout.splitlines():
    f = line.split()
    if len(f) == 4 and f[3].startswith('__CFUniChar'): syms[f[3]] = (int(f[0], 16), int(f[1], 16))
sections = []                                                          # Mach-O sections of the kernel, to say where a table lives
off = 32; ncmds = struct.unpack_from('<I', kernel, 16)[0]
for _ in range(ncmds):
    cmd, size = struct.unpack_from('<II', kernel, off)
    if cmd == 0x19:
        seg = kernel[off + 8:off + 24].split(b'\0')[0].decode(); nsects = struct.unpack_from('<I', kernel, off + 64)[0]
        for i in range(nsects):
            so = off + 72 + 80 * i; sn = kernel[so:so + 16].split(b'\0')[0].decode(); _, sz, fo = struct.unpack_from('<QQI', kernel, so + 32)
            sections.append((seg + ',' + sn, fo, sz))
    off += size
def where(o): return next((n for n, fo, sz in sections if fo and fo <= o < fo + sz), '?')
tab_rows, tabs = [], {}
for nm, (addr, size) in sorted(syms.items()):
    blob = harness[ro_off + addr - ro_addr:ro_off + addr - ro_addr + size]; tabs[nm] = blob
    n = kernel.count(blob); pos = kernel.find(blob)
    tab_rows.append((nm, size, hashlib.sha256(blob).hexdigest()[:16], n, hex(pos) if n else '-', where(pos) if n else '-'))
    check('tabla %s (%d bytes) del arnés compilado está en el kernel desplegado' % (nm, size), n >= 1, 'apariciones=%d offset=%s' % (n, hex(pos) if n else '-'))
check('se encontraron las 7 tablas CoreFoundation en el arnés', len(syms) == 7, str(sorted(syms)))
hdr = open(os.path.join(a.xnu_src, 'xnu/bsd/vfs/vfs_utfconvdata.h')).read()
for nm in ('__CFUniCharDecompositionTable', '__CFUniCharMultipleDecompositionTable'):
    mm = re.search(r'%s\[\]\s*=\s*\{(.*?)\};' % nm, hdr, re.S); vals = [int(x, 16) for x in re.findall(r'0x[0-9A-Fa-f]{1,4}', mm.group(1))]
    check('cabecera (texto) == bytes compilados en el arnés: %s' % nm, b''.join(v.to_bytes(2, 'little') for v in vals) == tabs[nm])
dec = struct.unpack('<%dH' % (len(tabs['__CFUniCharDecompositionTable']) // 2), tabs['__CFUniCharDecompositionTable'])
xnu_keys = set(dec[0::2])                                              # characters XNU decomposes through its table (Hangul is arithmetic)

# ------------------------------------------------------------------------------------------------------------------------------- Linux table
T = H.linux_table(a.ko)
check('tabla de Linux localizada y validada (é, À, ü)', H.linux_decomp(T, 0xE9) == [0x65, 0x301] and H.linux_decomp(T, 0xC0) == [0x41, 0x300] and H.linux_decomp(T, 0xFC) == [0x75, 0x308])
def linux_units(u):
    """hfsplus_asc2uni: ':' -> '/', U+2400 -> NUL, then (without nodecompose) decompose_unichar; surrogates are not modelled."""
    return H.linux_nfd_units([0x2F if x == 0x3A else (0 if x == 0x2400 else x) for x in u], T)
def linux_char(x): return H.linux_nfd_units([x], T)

# --------------------------------------------------------------------------------------------------------------------------------- the names
names = collections.OrderedDict()
for v in ('os', 'systemos', 'appos'):
    for l in open('%s/man_%s.jsonl' % (a.manifests, v)):
        d = json.loads(l); last = d['path'].rpartition('/')[2]; u = tuple(H.units(last))
        if H.nonascii_units(u): names.setdefault(u, d['path'])
nlist = list(names)
check('hay 329 nombres no ASCII distintos en los manifiestos', len(nlist) == 329, str(len(nlist)))
check('ninguno usa unidades suplentes (fuera del BMP)', not any(0xD800 <= x <= 0xDFFF for u in nlist for x in u))
xnu_out = run_harness([H.from_units(list(u)) for u in nlist])
check('XNU acepta los 329 nombres', all(o is not None for o in xnu_out))
xnu = dict(zip(nlist, xnu_out)); lin = {u: linux_units(list(u)) for u in nlist}
cat = H.catalog_names(a.catalog)
disk = {tuple(u) for _, u in cat}
check('el catálogo tiene nombres no ASCII cuyos bytes UTF-16 son todos < 0x80 (un filtro por bytes los perdería)',
      any(H.nonascii_units(u) and all(b < 0x80 for x in u for b in divmod(x, 256)) for _, u in cat),
      '%d nombres' % sum(1 for _, u in cat if H.nonascii_units(u) and all(b < 0x80 for x in u for b in divmod(x, 256))))
check('Linux: forma calculada con su tabla == nombre presente en el catálogo, para los 329', all(tuple(lin[u]) in disk for u in nlist),
      '%d/329' % sum(tuple(lin[u]) in disk for u in nlist))
nx = sum(tuple(xnu[u]) in disk for u in nlist)
check('XNU: forma calculada presente en el catálogo (se informa el recuento; no se exige 329)', True, '%d/329' % nx)
def posix(u): return H.from_units([0x2F if x == 0x3A else x for x in u])
check('XNU == NFD de Python (Unicode actual) para los 329', all(H.from_units(xnu[u]) == unicodedata.normalize('NFD', posix(u)) for u in nlist))
check('XNU == modelo hfs_names.xnu_nfd para los 329', all(H.from_units(xnu[u]) == H.xnu_nfd(posix(u)) for u in nlist))
diff = [u for u in nlist if lin[u] != xnu[u]]

# --------------------------------------------------------------------------------------------------------- per-character comparison tables
def canon32(x): return [ord(c) for c in H.xnu_nfd(chr(x))]
def compat32(x): return [ord(c) for c in unicodedata.ucd_3_2_0.normalize('NFKD', chr(x))]
def label(out, x):
    if out == [x]: return 'sin descomposición'
    if out == canon32(x): return 'NFD(3.2)'
    if out == compat32(x): return 'NFKD(3.2)'
    return 'otro: ni NFD ni NFKD'
def relation(L, X):
    sL, sX = H.from_units(L), H.from_units(X)
    if unicodedata.normalize('NFC', sL) == unicodedata.normalize('NFC', sX): return 'canónicamente equivalentes'
    if unicodedata.normalize('NFKC', sL) == unicodedata.normalize('NFKC', sX): return 'equivalentes solo por compatibilidad'
    return 'NO equivalentes'
HEAD = 'cp\tnombre Unicode\tnombres afectados\tentrada\tsalida Linux\tsalida XNU\tLinux tiene entrada\tXNU tiene entrada\tnivel Linux\tnivel XNU\trelación Linux/XNU\n'
def char_rows(chars, xnu_of, count=None):
    out = []
    for x in chars:
        L, X = linux_char(x), xnu_of[x]
        out.append(('U+%04X' % x, unicodedata.name(chr(x), '?'), (count or {}).get(x, ''), hx([x]), hx(L), hx(X), 'sí' if L != [x] else 'no',
                    'sí' if (x in xnu_keys or 0xAC00 <= x <= 0xD7A3) else 'no', label(L, x), label(X, x), relation(L, X)))
    return out
chars_in = sorted({x for u in nlist for x in u if x > 0x7F})
xnu_chars = dict(zip(chars_in, run_harness([chr(x) for x in chars_in])))
check('XNU acepta todos los caracteres no ASCII de los nombres', all(v is not None for v in xnu_chars.values()))
changed = [x for x in chars_in if linux_char(x) != xnu_chars[x]]
used = collections.Counter(x for u in diff for x in set(u) if x in set(changed))
open(a.out + '/diff_chars_in_names.tsv', 'w').write(HEAD + ''.join('\t'.join(str(c) for c in r) + '\n' for r in char_rows(changed, xnu_chars, used)))
bmp = [c for c in range(0x80, 0x10000) if not 0xD800 <= c <= 0xDFFF]
bx = dict(zip(bmp, run_harness([chr(c) for c in bmp])))
badx = [c for c in bmp if bx[c] is None]
check('XNU rechaza solo U+FFFE y U+FFFF en el BMP', badx == [0xFFFE, 0xFFFF], str([hex(c) for c in badx]))
bd = [c for c in bmp if bx[c] is not None and linux_char(c) != bx[c]]
open(a.out + '/bmp_diff_chars.tsv', 'w').write(HEAD + ''.join('\t'.join(str(c) for c in r) + '\n' for r in char_rows(bd, bx)))
check('todos los caracteres que cambian en los nombres están en la lista de diferencias del BMP', set(changed) <= set(bd))
check('cada nombre discrepante contiene al menos un carácter que cambia', all(set(u) & set(changed) for u in diff))
check('ningún nombre idéntico en Linux y XNU contiene un carácter que cambie', all(not (set(u) & set(changed)) for u in nlist if lin[u] == xnu[u]))
rows = []                                                              # per-name detail: input, Linux output, XNU output, first difference, level
for u in diff:
    L, X = lin[u], xnu[u]; i = next((k for k, (p, q) in enumerate(zip(L, X)) if p != q), min(len(L), len(X)))
    rows.append((names[u], hx(list(u)), hx(L), hx(X), i, relation(L, X), ' '.join('U+%04X' % x for x in sorted(set(u) & set(changed)))))
open(a.out + '/diff_names.tsv', 'w').write('ruta\tentrada (unidades UTF-16)\tsalida Linux\tsalida XNU\tíndice de la primera diferencia\trelación Linux/XNU\tcaracteres responsables\n' +
                                           ''.join('\t'.join(str(c) for c in r) + '\n' for r in rows))
open(a.out + '/names329.tsv', 'w').write('entrada\tNFC\tsalida XNU\tsalida Linux\tLinux en catálogo\tXNU en catálogo\n' + ''.join('%s\t%s\t%s\t%s\t%s\t%s\n' % (
    hx(list(u)), unicodedata.normalize('NFC', H.from_units(list(u))) == H.from_units(list(u)), hx(xnu[u]), hx(lin[u]), tuple(lin[u]) in disk, tuple(xnu[u]) in disk) for u in nlist))
open(a.out + '/tables_vs_kernel.tsv', 'w').write('tabla\tbytes\tsha256[:16]\tapariciones en el kernel\toffset\tsección\n' + ''.join('\t'.join(str(c) for c in r) + '\n' for r in tab_rows))

R = collections.OrderedDict(n_names=len(nlist), original_is_NFC=sum(unicodedata.normalize('NFC', H.from_units(list(u))) == H.from_units(list(u)) for u in nlist),
    Linux_form_in_catalog=sum(tuple(lin[u]) in disk for u in nlist), XNU_form_in_catalog=nx, Linux_equals_XNU=sum(lin[u] == xnu[u] for u in nlist), n_diff=len(diff),
    diff_by_relation=dict(collections.Counter(r[5] for r in rows)), chars_that_change_in_names=len(changed), bmp_chars_that_differ=len(bd), kernel_sha256=sha(a.kernel))
inputs = [a.catalog, a.xnu_harness, a.ko, a.kernel, os.path.join(a.xnu_src, 'xnu/bsd/vfs/vfs_utfconv.c'), os.path.join(a.xnu_src, 'xnu/bsd/vfs/vfs_utfconvdata.h'),
          os.path.join(a.xnu_src, 'xnu/bsd/sys/utfconv.h')] + ['%s/man_%s.jsonl' % (a.manifests, v) for v in ('os', 'systemos', 'appos')] + \
         [os.path.join(HERE, f) for f in ('compare_names.py', 'hfs_names.py', 'xnu_nfd.c', 'build_xnu_nfd.sh')]
open(a.out + '/inputs.sha256', 'w').write(''.join('%s  %s\n' % (sha(i), i) for i in inputs))
open(a.out + '/checks.tsv', 'w').write('resultado\tcomprobación\tdetalle\n' + ''.join('%s\t%s\t%s\n' % ('PASS' if ok else 'FAIL', n, d) for n, ok, d in CHECKS))
R['checks_pass'] = sum(ok for _, ok, _ in CHECKS); R['checks_fail'] = sum(not ok for _, ok, _ in CHECKS)
json.dump(R, open(a.out + '/results.json', 'w'), indent=1)
txt = json.dumps(R, indent=1) + '\n' + ('COMPARACIONES COMPLETADAS: las %d comprobaciones pasaron' % len(CHECKS) if R['checks_fail'] == 0 else 'COMPARACIONES CON FALLOS: %d' % R['checks_fail'])
open(a.out + '/summary.txt', 'w').write(txt + '\n'); print(txt)
for n, ok, d in CHECKS:
    if not ok: print('FAIL', n, d)
sys.exit(1 if R['checks_fail'] else 0)
