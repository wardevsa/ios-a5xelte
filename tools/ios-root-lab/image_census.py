#!/usr/bin/env python3
"""image_census.py MNT PERFIL : recuento de la imagen montada (ficheros, directorios, symlinks, bytes, nlink>1, inodos distintos, ficheros vacios,
setuid/sticky) y comprobacion de que no hay ficheros 'comprimidos' (flag UF_COMPRESSED no representable en Linux; se busca decmpfs/ResourceFork como xattr)."""
import sys, os, json, stat, collections
mnt, perfil = sys.argv[1:3]; c = collections.Counter(); inos = set(); ml = {}
for root, dirs, files in os.walk(mnt):
    for n in dirs + files:
        p = os.path.join(root, n); s = os.lstat(p)
        if stat.S_ISDIR(s.st_mode): c['dirs'] += 1
        elif stat.S_ISLNK(s.st_mode): c['symlinks'] += 1
        elif stat.S_ISREG(s.st_mode):
            c['nombres_reg'] += 1; inos.add((s.st_dev, s.st_ino))
            if s.st_nlink > 1: c['nombres_con_nlink>1'] += 1
            if s.st_size == 0: c['vacios'] += 1
            if s.st_mode & 0o4000: c['setuid'] += 1
            if s.st_mode & 0o2000: c['setgid'] += 1
        if stat.S_ISDIR(s.st_mode) and s.st_mode & 0o1000: c['sticky_dirs'] += 1
c['inodos_reg_distintos'] = len(inos)
tot = 0
for (d, i) in inos: pass
print(json.dumps(dict(perfil=perfil, **c)))
