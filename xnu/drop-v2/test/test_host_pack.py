#!/usr/bin/env python3
"""tools/herolte-drop.py (host) <-> herolte_drop_core.c (kernel): mismo formato, mismas reglas.

  python3 -I xnu/drop-v2/test/test_host_pack.py

Usa un `adb` simulado sobre un bytearray: no toca ningún dispositivo ni el repositorio.
"""
import hashlib
import importlib.util
import os
import re
import struct
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.argv = [sys.argv[0]]
import test_core as tc   # noqa: E402  (compila el núcleo y define Env/boot/initial)

spec = importlib.util.spec_from_file_location('herolte_drop', os.path.join(HERE, '..', '..', '..', 'tools', 'herolte-drop.py'))
host = importlib.util.module_from_spec(spec)
spec.loader.exec_module(host)
BLOCK = host.BLOCK


class FakeDev:
    def __init__(self, first):
        self.first = first
        self.mem = bytearray((first + host.DROP_BLOCKS + host.LOG_BLOCKS) * BLOCK)
        self.remote, self.writes = {}, []
        self.corrupt = None             # 'body' | 'head': cambia un byte al escribir

    def __call__(self, tool, *args, data=None):
        if args[0] == 'push':
            self.remote[args[2]] = open(args[1], 'rb').read()
            return b''
        cmd = args[1]
        if cmd.startswith('blockdev --getsize64'):
            return str(len(self.mem)).encode()
        m = re.fullmatch(r'dd if=/dev/zero of=\S+ bs=4096 seek=(\d+) count=1 conv=fsync', cmd)
        if m:
            n = int(m.group(1))
            self.mem[n * BLOCK:(n + 1) * BLOCK] = bytes(BLOCK)
            self.writes.append(('zero', n))
            return b''
        m = re.fullmatch(r'dd if=(/tmp/\S+) of=\S+ bs=4096 seek=(\d+) conv=fsync', cmd)
        if m:
            name, n = m.group(1), int(m.group(2))
            d = bytearray(self.remote[name])
            assert len(d) % BLOCK == 0
            if self.corrupt and self.corrupt in name:
                d[len(d) // 2] ^= 1
            self.mem[n * BLOCK:n * BLOCK + len(d)] = d
            self.writes.append(('write', n, len(d) // BLOCK))
            return b''
        m = re.fullmatch(r'dd if=\S+ bs=4096 skip=(\d+) count=(\d+) 2>/dev/null \| sha256sum', cmd)
        if m:
            s, c = int(m.group(1)), int(m.group(2))
            return (hashlib.sha256(bytes(self.mem[s * BLOCK:(s + c) * BLOCK])).hexdigest() + '  -\n').encode()
        if cmd.startswith('rm -f'):
            self.remote.pop(cmd.split()[-1], None)
            return b''
        raise AssertionError(f'comando no previsto: {cmd}')


def macho():
    return struct.pack('<IIIIIIII', 0xFEEDFACF, 0x0100000C, 0, 2, 0, 0, 0, 0)


def run_main(dev, argv):
    host.adb = dev
    old = sys.argv
    sys.argv = ['herolte-drop.py', 'adb'] + argv
    try:
        return host.main()
    finally:
        sys.argv = old


def zone_of(dev):
    return bytes(dev.mem[dev.first * BLOCK:(dev.first + host.DROP_BLOCKS) * BLOCK])


def main():
    bad = []

    def check(name, ok, detail=''):
        print(f'  [{"OK" if ok else "FALLA"}] {name}{(" — " + detail) if detail and not ok else ""}')
        if not ok:
            bad.append(name)

    with tempfile.TemporaryDirectory(prefix='hostpack-') as d:
        auto = os.path.join(d, 'autorun')
        lib = os.path.join(d, 'libfoo.dylib')
        open(auto, 'wb').write(b'#!/bin/sh\necho hi\n')
        os.chmod(auto, 0o755)
        open(lib, 'wb').write(os.urandom(300_000))
        app = os.path.join(d, 'Foo.app')
        os.makedirs(app + '/Frameworks')
        open(app + '/Foo', 'wb').write(macho() + b'\0' * 100)
        open(app + '/Info.plist', 'wb').write(b'<plist/>')
        os.chdir(d)

        print('Escritura de la zona con adb simulado')
        dev = FakeDev(10)
        rc = run_main(dev, ['autorun=' + auto, 'lib/libfoo.dylib=' + lib, 'app=' + app])
        nblk = dev.writes[1][2]
        check('main() termina bien', rc == 0)
        check('orden: cabecera a cero, payload, cabecera sola',
              dev.writes == [('zero', 10), ('write', 11, nblk), ('write', 10, 1)], str(dev.writes))
        check('no deja ficheros temporales del anfitrión en el directorio actual', not os.listdir(d) or
              set(os.listdir(d)) == {'autorun', 'libfoo.dylib', 'Foo.app'}, str(os.listdir(d)))

        print('\nEl núcleo C acepta lo que escribió el anfitrión')
        zone = zone_of(dev)
        f = tc.initial()
        env = tc.Env(f, zone)
        rc = tc.boot(env)
        st = tc.parse_state(f.read(tc.D + '/state'))
        R = tc.ROOT + '/'
        check('instala y publica ready', rc == 0 and st and st['phase'] == 3, '; '.join(env.logs))
        check('autorun con su contenido', f.read(R + 'autorun') == open(auto, 'rb').read())
        check('biblioteca con su contenido', f.read(R + 'lib/libfoo.dylib') == open(lib, 'rb').read())
        check('app: ejecutable e Info.plist en apps/Foo.app',
              f.read(R + 'apps/Foo.app/Foo') == macho() + b'\0' * 100 and f.read(R + 'apps/Foo.app/Info.plist') == b'<plist/>')
        check('límite conocido del anfitrión (ya existía en v1): no emite directorios vacíos',
              (R + 'apps/Foo.app/Frameworks') not in f.dirs)
        P = tc.ROOT + '/'
        ents = [(P + 'apps', 0, b''), (P + 'apps/Z.app', 0, b''), (P + 'apps/Z.app/Empty', 0, b''),
                (P + 'apps/Z.app/Z', 0o755, b'z')]
        f2 = tc.initial()
        tc.boot(tc.Env(f2, tc.raw_zone(tc.raw_payload(ents), len(ents), 3)))
        check('el núcleo sí conserva un directorio vacío si el paquete lo trae', (P + 'apps/Z.app/Empty') in f2.dirs)

        print('\nIdentidad, generación y reinstalación')
        snap, ops0 = f.snapshot(), f.ops
        tc.boot(tc.Env(f, zone))
        check('mismo contenido y generación: no se reinstala', f.snapshot() == snap and f.ops == ops0)
        dev2 = FakeDev(10)
        run_main(dev2, ['autorun=' + auto, '--generation', '5'])
        zone2 = zone_of(dev2)
        check('la generación va en la cabecera', struct.unpack_from('<Q', zone2, 24)[0] == 5)
        dev3 = FakeDev(10)
        run_main(dev3, ['autorun=' + auto, '--force'])
        check('--force usa una generación distinta de 1', struct.unpack_from('<Q', zone_of(dev3), 24)[0] > 1)

        print('\nFallos de escritura: la cabecera no queda sobre un payload dañado')
        for which in ('body', 'head'):
            dev = FakeDev(10)
            dev.mem[10 * BLOCK:10 * BLOCK + 8] = b'HERODRP2'      # había un paquete anterior
            dev.corrupt = which
            rc = run_main(dev, ['autorun=' + auto])
            check(f'corrupción al escribir {which}: exit 1 y cabecera a cero',
                  rc == 1 and dev.mem[10 * BLOCK:11 * BLOCK] == bytes(BLOCK), f'rc={rc}')
        dev = FakeDev(10)
        run_main(dev, ['autorun=' + auto])
        run_main(dev, ['--clear'])
        check('--clear deja la cabecera a cero', dev.mem[10 * BLOCK:11 * BLOCK] == bytes(BLOCK))

        print('\nEl anfitrión y el núcleo rechazan lo mismo (rutas)')
        for dest in ('../x', '.drop/state', 'a//b', '/abs', 'a\\b'):
            try:
                host.pack([(dest, auto)])
                check(f'host rechaza {dest!r}', False)
            except host.DropError:
                check(f'host rechaza {dest!r}', True)
        os.chdir(tempfile.gettempdir())

    print(f'\n{"FALLAN: " + ", ".join(bad) if bad else "todo correcto"}')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
