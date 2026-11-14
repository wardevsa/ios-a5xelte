"""Sistema de ficheros en memoria con cortes de alimentación (modelo pesimista).

Supuestos (ver xnu/drop-v2/README.md, "Garantías"):
  * Los metadatos (mkdir/create/rename/unlink) se persisten como un PREFIJO del orden emitido
    desde la última barrera (orden del journal de HFS).
  * Los datos de fichero NO van por el journal: un inodo escrito después de la última barrera
    puede aparecer, tras un corte, con contenido TORN aunque su nombre haya persistido.
  * barrier() es la única garantía de durabilidad (F_FULLFSYNC + sync directo del dispositivo).
"""
import random

TORN = b'\x00<TORN>\x00'


class Crash(Exception):
    pass


class BarrierFail(Exception):
    pass


class FS:
    def __init__(s):
        s.dirs = {'/'}
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
                for q in [q for q in dirs if q == a or q.startswith(a + '/')]:
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
            s.ino[i] = {'v': b'', 'dur': False}
        else:
            s.tick()
            i = s.nxt
            s.nxt += 1
            s.ino[i] = {'v': b'', 'dur': False}
            s.do(('create', p, i))
        s.tick()
        s.ino[i]['v'] = data
        s.ino[i]['dur'] = False

    def set_data(s, p, data):               # segunda mitad de write_new, para escrituras por trozos
        s.tick()
        i = s.ns[p]
        s.ino[i]['v'] = data
        s.ino[i]['dur'] = False

    def rename(s, a, b):
        s.mkdir_p(s.parent(b))
        if a in s.dirs and b in s.dirs:     # POSIX: solo sobre un directorio vacío
            if any(q.startswith(b + '/') for q in list(s.dirs) + list(s.ns)):
                raise OSError(39, 'ENOTEMPTY')
        if a not in s.ns and a not in s.dirs:
            raise OSError(2, 'ENOENT')
        s.tick()
        s.do(('rename', a, b))

    def unlink(s, p):
        if p not in s.ns:
            raise OSError(2, 'ENOENT')
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
        """Estado en disco tras un corte: base + los p primeros metadatos pendientes."""
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
            else:                           # variante aleatoria reproducible, por inodo
                keep = random.Random(f'{mode}:{salt}:{i}').random() < 0.5
            n.ino[i] = {'v': d['v'] if keep else TORN, 'dur': True}
        n.base = (set(dirs), dict(ns))
        return n

    def snapshot(s):
        return (sorted((p, s.read(p)) for p in s.ns), sorted(s.dirs))
