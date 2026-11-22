#!/usr/bin/env python3
"""image_xattr_check.py MNT : ningun fichero debe llevar los xattr com.apple.decmpfs / com.apple.ResourceFork (contenido ya materializado) ni
sidecars ':com.apple.*' de 7z. Lista el resto de xattr presentes (Linux hfsplus los expone como user./trusted.)."""
import sys, os, json, collections
mnt = sys.argv[1]; c = collections.Counter(); bad = []
for root, dirs, files in os.walk(mnt):
    for n in dirs + files:
        if ':com.apple.' in n: c['sidecar_7z'] += 1; bad.append(os.path.join(root, n))
        p = os.path.join(root, n)
        try: xs = os.listxattr(p, follow_symlinks=False)
        except OSError as e: c['listxattr_err_' + str(e.errno)] += 1; continue
        for x in xs:
            c['xattr:' + x] += 1
            if 'decmpfs' in x or 'ResourceFork' in x: bad.append(p + '  ' + x)
print(json.dumps(dict(c)))
for b in bad[:10]: print('  ', b)
sys.exit(1 if bad else 0)
