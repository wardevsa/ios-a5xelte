"""guard.py: comprobaciones de seguridad para operar con privilegios SOLO sobre una imagen de laboratorio montada (T04-R).
assert_lab_mount(mount_point, image): exige que mount_point sea un punto de montaje de tipo hfsplus cuyo origen sea un dispositivo
loop respaldado por el fichero `image` (backing_file); nunca un disco fisico. Con test_fakeroot=True (solo pruebas de laboratorio sin
privilegios) exige FAKEROOTKEY y NO exige montaje."""
import os, sys

def _mountinfo():
    out = []
    for ln in open('/proc/self/mountinfo'):
        a, _, b = ln.partition(' - ')
        f = a.split(); g = b.split()
        out.append(dict(mp=f[4].replace('\\040', ' '), fstype=g[0], src=g[1]))
    return out

def assert_lab_mount(mount_point, image, test_fakeroot=False):
    if test_fakeroot:
        if 'FAKEROOTKEY' not in os.environ: sys.exit('GUARD: --test-fakeroot exige FAKEROOTKEY')
        return
    if os.geteuid() != 0: sys.exit('GUARD: se requiere root (sudo) para operar sobre la imagen montada')
    mp = os.path.realpath(mount_point); img = os.path.realpath(image)
    if not os.path.isfile(img): sys.exit('GUARD: la imagen %s no es un fichero regular' % img)
    cand = [m for m in _mountinfo() if os.path.realpath(m['mp']) == mp]
    if not cand: sys.exit('GUARD: %s no es un punto de montaje' % mp)
    m = cand[-1]
    if m['fstype'] != 'hfsplus': sys.exit('GUARD: %s no es hfsplus (%s)' % (mp, m['fstype']))
    if not m['src'].startswith('/dev/loop'): sys.exit('GUARD: origen %s no es un dispositivo loop' % m['src'])
    bf = '/sys/block/%s/loop/backing_file' % os.path.basename(m['src'])
    try: back = os.path.realpath(open(bf).read().strip())
    except OSError as e: sys.exit('GUARD: no se pudo leer %s (%s)' % (bf, e))
    if back != img: sys.exit('GUARD: %s esta respaldado por %s, no por la imagen de laboratorio %s' % (m['src'], back, img))

def assert_under(root, mount_point):
    r = os.path.realpath(root); m = os.path.realpath(mount_point)
    if r != m and not r.startswith(m + '/'): sys.exit('GUARD: %s no esta dentro de %s' % (r, m))
