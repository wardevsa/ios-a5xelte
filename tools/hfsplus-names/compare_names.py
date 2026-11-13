#!/usr/bin/env python3
"""Three-level comparison of how a name is stored on HFS+: XNU (its own utf8_decodestr), Linux hfsplus (its own decompose table), and the lab image.
READ-ONLY: opens the audit catalog, the manifests, the hfsplus module and the kernel; writes only into --out (must not exist).
  compare_names.py --catalog catalog.jsonl --manifests DIR(man_{os,systemos,appos}.jsonl) --xnu-harness xnu_nfd --ko hfsplus.ko[.zst]
                   [--kernel kernel.development.herolte --xnu-src DIR(with xnu/bsd/vfs/vfs_utfconvdata.h)] --out NEWDIR
Output: NEWDIR/results.json, NEWDIR/names329.tsv, NEWDIR/diff32.tsv, NEWDIR/inputs.sha256, NEWDIR/summary.txt (file names are Apple's data: keep this off git)."""
import argparse, collections, hashlib, json, os, re, subprocess, sys, unicodedata
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hfs_names as H

ap = argparse.ArgumentParser()
for a in ('catalog', 'manifests', 'xnu-harness', 'ko', 'out'): ap.add_argument('--' + a, required=True)
ap.add_argument('--kernel'); ap.add_argument('--xnu-src')
a = ap.parse_args()
os.makedirs(a.out)                                                     # refuses to reuse an existing directory
sha = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
cps = lambda s: ' '.join('%04X' % ord(c) for c in s)
nonascii = lambda s: ' '.join('%04X' % ord(c) for c in s if ord(c) > 127)
T = H.linux_table(a.ko)

# --- names: every non-ASCII last component of the three manifests, as the manifest (7z/APFS) gives it
names = collections.OrderedDict()
for v in ('os', 'systemos', 'appos'):
    for l in open('%s/man_%s.jsonl' % (a.manifests, v)):
        d = json.loads(l); last = d['path'].rpartition('/')[2]
        if any(ord(c) > 127 for c in last): names.setdefault(last, d['path'])
lst = list(names)
p = subprocess.run([a.xnu_harness], input='\n'.join(lst) + '\n', capture_output=True, text=True, check=True)   # raw UTF-8 names, ':' handled by XNU itself
xnu = {}
for s, line in zip(lst, p.stdout.splitlines()):
    f = line.split(); assert f[0] == '0', (s, line); xnu[s] = ''.join(chr(int(x, 16)) for x in f[1:])
disk = collections.Counter(bytes.fromhex(json.loads(l)['raw']) for l in open(a.catalog))
disk16 = {k.decode('utf-16-be', 'surrogatepass') for k in disk}      # decoded, so combining marks such as U+0301 (bytes 03 01) are not lost

R = collections.OrderedDict()
R['n_names'] = len(lst)
R['original_is_NFC'] = sum(unicodedata.normalize('NFC', s) == s for s in lst)
R['original_is_NFD'] = sum(unicodedata.normalize('NFD', s) == s for s in lst)
R['XNU_equals_python_NFD_current_unicode'] = sum(xnu[s] == unicodedata.normalize('NFD', s.replace(':', '/')) for s in lst)
R['XNU_equals_hfs_names.xnu_nfd_model'] = sum(xnu[s] == H.xnu_nfd(s.replace(':', '/')) for s in lst)
lin = {s: H.linux_nfd(s.replace(':', '/'), T) for s in lst}
R['Linux_form_is_on_disk'] = sum(lin[s] in disk16 for s in lst)
R['XNU_form_is_on_disk'] = sum(xnu[s] in disk16 for s in lst)
R['Linux_equals_XNU'] = sum(lin[s] == xnu[s] for s in lst)
R['disk_bytes_equal_Linux_form_UTF16BE'] = sum(lin[s].encode('utf-16-be', 'surrogatepass') in disk for s in lst)
diff = [s for s in lst if lin[s] != xnu[s]]
R['n_diff'] = len(diff)
kinds = collections.Counter(); rows = []
for s in diff:
    L, X = lin[s], xnu[s]
    canon = unicodedata.normalize('NFC', L) == unicodedata.normalize('NFC', X)
    compat = unicodedata.normalize('NFKC', L) == unicodedata.normalize('NFKC', X)
    k = 'canonicamente_equivalentes' if canon else ('equivalentes_solo_por_compatibilidad' if compat else 'NO_equivalentes')
    kinds[k] += 1
    first = next(((x, y) for x, y in zip(L, X) if x != y), (L[len(X):][:1] or '-', ''))
    rows.append((s, names[s], nonascii(s), nonascii(L), nonascii(X), k, 'U+%04X→U+%04X' % (ord(first[0]), ord(first[1])) if first[1] else '-'))
R['diff_kinds'] = dict(kinds)
R['diff_first_difference'] = dict(collections.Counter(r[6] for r in rows))
# encoding/representation: ':' and U+2400 are handled by both sides alike?  (only counted, not part of the 32)
R['names_with_colon'] = sum(':' in s for s in lst)
R['colon_names_equal_in_both'] = sum(lin[s] == xnu[s] for s in lst if ':' in s)
# kernel cross-check: XNU's decomposition tables as compiled in the harness are present, byte for byte, in the deployed kernel
if a.kernel and a.xnu_src:
    hdr = open(os.path.join(a.xnu_src, 'xnu/bsd/vfs/vfs_utfconvdata.h')).read(); kern = open(a.kernel, 'rb').read(); chk = {}
    for nm in ('__CFUniCharDecompositionTable', '__CFUniCharMultipleDecompositionTable'):
        m = re.search(r'%s\[\]\s*=\s*\{(.*?)\};' % nm, hdr, re.S)
        vals = [int(x, 16) for x in re.findall(r'0x[0-9A-Fa-f]{1,4}', m.group(1))] if m else []
        blob = b''.join(v.to_bytes(2, 'little') for v in vals)
        chk[nm] = dict(entries=len(vals), found_in_kernel=bool(vals) and blob in kern, kernel_offset=hex(kern.find(blob)) if vals and blob in kern else None)
    R['kernel_tables'] = chk; R['kernel_sha256'] = sha(a.kernel)
inputs = [a.catalog, a.xnu_harness, a.ko] + ['%s/man_%s.jsonl' % (a.manifests, v) for v in ('os', 'systemos', 'appos')]
if a.xnu_src: inputs += [os.path.join(a.xnu_src, 'xnu/bsd/vfs/' + f) for f in ('vfs_utfconv.c', 'vfs_utfconvdata.h')]
open(a.out + '/inputs.sha256', 'w').write(''.join('%s  %s\n' % (sha(i), i) for i in inputs))
json.dump(R, open(a.out + '/results.json', 'w'), indent=1)
open(a.out + '/names329.tsv', 'w').write('manifiesto_cp\tNFC?\tNFD_python_cp\tXNU_cp\tLinux_cp\ten_disco_Linux\ten_disco_XNU\n' + ''.join(
    '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (nonascii(s), unicodedata.normalize('NFC', s) == s, nonascii(unicodedata.normalize('NFD', s)), nonascii(xnu[s]), nonascii(lin[s]), lin[s] in disk16, xnu[s] in disk16) for s in lst))
open(a.out + '/diff32.tsv', 'w').write('ruta\tmanifiesto_cp\tLinux_cp\tXNU_cp\tclase\tprimera_diferencia\n' + ''.join('%s\t%s\t%s\t%s\t%s\t%s\n' % (r[1], r[2], r[3], r[4], r[5], r[6]) for r in rows))
open(a.out + '/summary.txt', 'w').write(json.dumps(R, indent=1))
print(json.dumps(R, indent=1))
