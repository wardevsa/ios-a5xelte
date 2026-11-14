#!/usr/bin/env python3
"""hfsx_check.py IMG [--profile P] [--census-file F] [--names-out F] [--expect-hfsx]
Lee (SOLO LECTURA, imagen desmontada) la estructura on-disk HFS+/HFSX y comprueba:
  - firma y version del volume header (HX/5 = HFSX), atributos (journaled 0x2000, unmounted 0x100, inconsistent 0x800)
  - keyCompareType del BTHeaderRec del catalogo (0xBC = kHFSBinaryCompare = SENSIBLE a mayusculas; 0xCF = kHFSCaseFolding): NO se deduce de la firma
  - recorrido de las hojas del catalogo: carpetas, ficheros, symlinks ('slnk'), hardlinks REALES ('hlnk'/'hfs+' -> iNode<N> en '\\0\\0\\0\\0HFS+ Private Data'),
    hlnk colgantes, iNode huerfanos
  - nombres: los que contienen '/' en disco (= ':' POSIX), y los no ASCII (forma almacenada) frente a NFD(manifiesto)
exit 0 si todo lo exigido se cumple."""
import sys, struct, json, argparse, collections, unicodedata, os
ap = argparse.ArgumentParser(); ap.add_argument('img'); ap.add_argument('--profile', default='full'); ap.add_argument('--census-file'); ap.add_argument('--names-out'); ap.add_argument('--expect-hfsx', action='store_true'); ap.add_argument('--no-manifest', action='store_true', help='sin expectativas de nombres (pruebas de comportamiento)'); a = ap.parse_args()
f = open(a.img, 'rb')
def rd(off, n): f.seek(off); return f.read(n)
vh = rd(1024, 512); sig, ver = struct.unpack('>2sH', vh[:4]); attrs = struct.unpack('>I', vh[4:8])[0]; blk = struct.unpack('>I', vh[40:44])[0]; total = struct.unpack('>I', vh[44:48])[0]
def fork(off):
    logical, clump, tb = struct.unpack('>QII', vh[off:off + 16]); return logical, tb, [struct.unpack('>II', vh[off + 16 + 8 * i: off + 24 + 8 * i]) for i in range(8)]
EXT_OFF, CAT_OFF = 192, 272
def read_extents(exts, limit=None):
    out = []
    for s, c in exts:
        if c: out.append(rd(s * blk, c * blk))
    return b''.join(out)
def btree_nodes(data):
    ns = struct.unpack('>H', data[32:34])[0]; kct = data[51]; first = struct.unpack('>I', data[24:28])[0]
    return ns, kct, first
def leaf_records(data, ns, first):
    node = first
    while node:
        nd = data[node * ns:(node + 1) * ns]; flink = struct.unpack('>I', nd[0:4])[0]; kind = struct.unpack('>b', nd[8:9])[0]; n = struct.unpack('>H', nd[10:12])[0]
        if kind != -1: break
        for i in range(n):
            o = struct.unpack('>H', nd[ns - 2 * (i + 1): ns - 2 * i])[0]; yield nd, o
        node = flink
# arbol de extents overflow (para catalogos fragmentados > 8 extents)
ext_logical, ext_tb, ext_ex = fork(EXT_OFF); ext_data = read_extents(ext_ex)
overflow = collections.defaultdict(list)
if ext_data:
    ns_e, _, first_e = btree_nodes(ext_data)
    for nd, o in leaf_records(ext_data, ns_e, first_e):
        kl = struct.unpack('>H', nd[o:o + 2])[0]
        if kl != 10: continue
        ftype, _, fid, start = struct.unpack('>BBII', nd[o + 2:o + 12]); d = o + 2 + kl
        overflow[(fid, ftype)].append((start, [struct.unpack('>II', nd[d + 8 * i: d + 8 * i + 8]) for i in range(8)]))
cat_logical, cat_tb, cat_ex = fork(CAT_OFF); exts = list(cat_ex)
have = sum(c for _, c in exts)
if have < cat_tb:
    for start, ex in sorted(overflow.get((4, 0), [])): exts += ex
cat = read_extents(exts)[:cat_logical]
ns, kct, first = btree_nodes(cat)
res = dict(image=os.path.basename(a.img), signature=sig.decode('latin1'), version=ver, block_size=blk, total_blocks=total, attributes=hex(attrs),
           journaled=bool(attrs & 0x2000), cleanly_unmounted=bool(attrs & 0x100), inconsistent_flag=bool(attrs & 0x800),
           catalog_node_size=ns, keyCompareType=hex(kct), key_compare=('binary(case-sensitive)' if kct == 0xBC else 'case-folding(case-insensitive)' if kct == 0xCF else 'desconocido'),
           catalog_extents=len(exts), catalog_overflow_used=have < cat_tb)
cnt = collections.Counter(); names_slash = []; nonascii = []; hl_inodes = collections.Counter(); inode_files = {}; priv_id = None; rows = []
folders = {}
for nd, o in leaf_records(cat, ns, first):
    kl = struct.unpack('>H', nd[o:o + 2])[0]; parent = struct.unpack('>I', nd[o + 2:o + 6])[0]; nl = struct.unpack('>H', nd[o + 6:o + 8])[0]
    name = nd[o + 8:o + 8 + 2 * nl].decode('utf-16-be', 'surrogatepass'); d = o + 2 + kl
    if d & 1: d += 1
    rt = struct.unpack('>h', nd[d:d + 2])[0]
    if rt == 1:
        cnt['folders'] += 1; fid = struct.unpack('>I', nd[d + 8:d + 12])[0]; folders[fid] = (parent, name)
        if parent == 2 and name.startswith('\x00\x00\x00\x00HFS+ Private Data'): priv_id = fid
    elif rt == 2:
        cnt['files'] += 1; fid = struct.unpack('>I', nd[d + 8:d + 12])[0]; ftype, fcr = struct.unpack('>II', nd[d + 48:d + 56]); special = struct.unpack('>I', nd[d + 44:d + 48])[0]
        if ftype == 0x686C6E6B and fcr == 0x6866732B: cnt['hlnk'] += 1; hl_inodes[special] += 1
        elif ftype == 0x736C6E6B: cnt['symlinks_slnk'] += 1
        if parent == priv_id and name.startswith('iNode'):
            cnt['iNode_files'] += 1
            try: inode_files[int(name[5:])] = fid
            except ValueError: pass
    else: continue
    if '/' in name: names_slash.append((parent, name))
    if any(ord(ch) > 127 for ch in name): nonascii.append((parent, name))
res.update(dict(cnt))
res['hlnk_distinct_inodes'] = len(hl_inodes)
res['hlnk_dangling'] = sum(1 for i in hl_inodes if i not in inode_files)
res['iNode_orphans'] = sum(1 for i in inode_files if i not in hl_inodes)
res['private_data_dir_found'] = priv_id is not None
res['names_with_slash_on_disk(=colon_posix)'] = len(names_slash)
res['names_nonascii_on_disk'] = len(nonascii)
# expectativas desde los manifiestos
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); import xnu_name_adapter
SC = os.path.join(os.environ.get('IOS_ROOT_LAB') or sys.exit('IOS_ROOT_LAB'), 'out')
def man(v): return xnu_name_adapter.translate_manifest([json.loads(l) for l in open(os.path.join(SC, 'man_%s.jsonl' % v))], xnu_name_adapter.load_exclusions())
scope = None
if a.no_manifest: pass
elif a.profile.startswith('mini'):
    sc = os.path.join(os.path.dirname(SC), 'work', 'os', 'scope.lst'); scope = {l.rstrip('\n') for l in open(sc, encoding='utf-8', errors='surrogateescape') if l.strip()}
exp_colon, exp_nfd = collections.Counter(), collections.Counter()
for v in ([] if a.no_manifest else ['os', 'systemos', 'appos'] if a.profile.startswith('full') else ['os', 'appos']):
    for d in man(v):
        if v == 'os' and scope is not None and d['path'] not in scope: continue
        if d['type'] == 'dir' and False: continue
        last = d['path'].rpartition('/')[2]
        if ':' in last: exp_colon[(v, d['path'])] += 1
        if any(ord(ch) > 127 for ch in last): exp_nfd[last.replace(':', '/')] += 1       # el manifiesto ya viene en forma XNU (adaptador); el ':' POSIX es '/' en disco
res['expected_colon_names_from_manifests'] = len(exp_colon)
disk_nonascii = collections.Counter(n for _, n in nonascii)
miss = [n for n in exp_nfd if disk_nonascii[n] == 0]; extra = [n for n in disk_nonascii if n not in exp_nfd]
res['nonascii_expected_nfd_distinct'] = len(exp_nfd); res['nonascii_nfd_found_exact'] = len(exp_nfd) - len(miss); res['nonascii_nfd_missing_on_disk'] = len(miss); res['nonascii_on_disk_not_expected'] = len(extra)
if a.census_file and os.path.exists(a.census_file):
    c = json.loads(open(a.census_file).read().splitlines()[0]); res['census_nombres_con_nlink>1'] = c.get('nombres_con_nlink>1'); res['hlnk_equals_census'] = (c.get('nombres_con_nlink>1') == cnt['hlnk'])
if a.names_out:
    with open(a.names_out, 'w', encoding='utf-8', errors='surrogateescape') as o:
        for p, n in names_slash: o.write('SLASH\t%d\t%r\n' % (p, n))
        for n in miss[:200]: o.write('NFD-ESPERADO-AUSENTE\t%r\t%s\n' % (n, [hex(ord(c)) for c in n if ord(c) > 127][:6]))
        for n in extra[:200]: o.write('NO-ESPERADO\t%r\n' % n)
errs = []
if a.expect_hfsx:
    if sig != b'HX' or ver != 5: errs.append('firma/version no es HX/5')
    if kct != 0xBC: errs.append('keyCompareType != 0xBC (no es sensible a mayusculas)')
if not res['journaled']: errs.append('sin journal')
if res['inconsistent_flag']: errs.append('flag de inconsistencia activo')
if cnt['hlnk'] and (res['hlnk_dangling'] or res['iNode_orphans'] or not res['private_data_dir_found']): errs.append('hardlinks incoherentes (colgantes/huerfanos/sin directorio privado)')
if not a.no_manifest and len(names_slash) != len(exp_colon): errs.append('nombres con ":" esperados %d != %d en disco con "/"' % (len(exp_colon), len(names_slash)))
if not a.no_manifest and (miss or extra): errs.append('nombres no ASCII: %d NFD esperados ausentes, %d inesperados' % (len(miss), len(extra)))
if res.get('hlnk_equals_census') is False: errs.append('hlnk en catalogo != nombres con nlink>1 en el montaje')
if a.no_manifest: res['slash_names'] = [n for _, n in names_slash][:10]; res['nonascii_names'] = [(n, [hex(ord(c)) for c in n if ord(c) > 127]) for _, n in nonascii][:10]; res['all_names_sample'] = sorted({n for _, n in nonascii + names_slash})[:10]
res['errores'] = errs
print(json.dumps(res, sort_keys=True))
sys.exit(1 if errs else 0)
