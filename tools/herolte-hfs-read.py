#!/usr/bin/env python3
"""Read-only HFS+/HFSX reader over adb (the S7's iOS root on USERDATA, from TWRP).

  herolte-hfs-read.py ls   PATH            list a directory
  herolte-hfs-read.py get  PATH OUT        copy a file (data fork; decmpfs not handled)
  herolte-hfs-read.py stat PATH

Environment: HEROLTE_ADB (adb path), ANDROID_SERIAL. Output may be Apple's files: keep it off Git.

Only `dd if=DEV` reads, through `adb exec-out`. Never writes to the device.
"""
import struct, subprocess, sys, os

ADB = os.environ.get('HEROLTE_ADB', 'adb')
SERIAL = os.environ.get('ANDROID_SERIAL', '')
DEV = '/dev/block/sda18'


class Dev:
    def __init__(self):
        self.cache = {}

    def read(self, off, n):
        """Bytes [off, off+n) of the partition, read in 1 MiB chunks."""
        CH = 1 << 20
        out = bytearray()
        pos = off
        while pos < off + n:
            c = pos // CH
            if c not in self.cache:
                if len(self.cache) > 256:
                    self.cache.clear()
                data = subprocess.run([ADB] + (['-s', SERIAL] if SERIAL else []) + ['exec-out',
                                       f'dd if={DEV} bs={CH} skip={c} count=1 2>/dev/null'],
                                      check=True, capture_output=True).stdout
                self.cache[c] = data
            chunk = self.cache[c]
            s = pos - c * CH
            take = min(CH - s, off + n - pos)
            out += chunk[s:s + take]
            pos += take
        return bytes(out)

    def read_big(self, off, n, fh):
        """Stream n bytes at off into fh, 16 MiB per dd."""
        CH = 16 << 20
        done = 0
        while done < n:
            take = min(CH, n - done)
            # dd granularity: 4 KiB blocks; off is block aligned for extents
            bs = 4096
            assert (off + done) % bs == 0
            cnt = (take + bs - 1) // bs
            data = subprocess.run([ADB] + (['-s', SERIAL] if SERIAL else []) + ['exec-out',
                                   f'dd if={DEV} bs={bs} skip={(off + done) // bs} count={cnt} 2>/dev/null'],
                                  check=True, capture_output=True).stdout
            fh.write(data[:take])
            done += take


def be(fmt, b, o=0):
    return struct.unpack_from('>' + fmt, b, o)


class HFS:
    def __init__(self, dev):
        self.d = dev
        vh = dev.read(1024, 512)
        sig = vh[:2]
        assert sig in (b'H+', b'HX'), sig
        self.bs, = be('I', vh, 40)
        # forks: allocation 112, extents 192, catalog 272, attributes 352
        self.cat_fork = self.fork(vh, 272)
        self.ext_fork = self.fork(vh, 192)
        self.hfsx = sig == b'HX'
        self.cat = BTree(self, self.cat_fork, 4)
        self.ext = BTree(self, self.ext_fork, 3)

    def fork(self, b, o):
        size, = be('Q', b, o)
        ext = [be('II', b, o + 16 + 8 * i) for i in range(8)]
        return size, [e for e in ext if e[1]]

    def fork_read(self, fork, off, n, fileid=None, ftype=0):
        size, exts = fork
        exts = self.all_extents(exts, fileid, ftype)
        out = bytearray()
        for start, count in exts:
            ebytes = count * self.bs
            if off >= ebytes:
                off -= ebytes
                continue
            take = min(ebytes - off, n - len(out))
            out += self.d.read(start * self.bs + off, take)
            off = 0
            if len(out) >= n:
                break
        return bytes(out)

    def all_extents(self, exts, fileid, ftype):
        total = sum(c for _, c in exts)
        if fileid is None or len(exts) < 8:
            return exts
        exts = list(exts)
        while True:
            more = self.ext_lookup(fileid, ftype, total)
            if not more:
                return exts
            exts += more
            total += sum(c for _, c in more)

    def ext_lookup(self, fileid, ftype, startblock):
        key = (ftype, fileid, startblock)
        for k, rec in self.ext.records():
            klen, = be('H', k, 0)
            kt, _, kid, kstart = be('BBII', k, 2)
            if (kt, kid, kstart) == key:
                return [e for e in (be('II', rec, 8 * i) for i in range(8)) if e[1]]
        return None


class BTree:
    def __init__(self, fs, fork, fileid):
        self.fs, self.fork, self.fid = fs, fork, fileid
        hdr = fs.fork_read(fork, 0, 512)
        self.root, = be('I', hdr, 14 + 2)
        self.first_leaf, = be('I', hdr, 14 + 10)
        self.node_size, = be('H', hdr, 14 + 18)
        self.nodes = {}

    def node(self, n):
        if n not in self.nodes:
            self.nodes[n] = self.fs.fork_read(self.fork, n * self.node_size, self.node_size,
                                              self.fid if self.fid == 4 else None)
        return self.nodes[n]

    def recs(self, nd):
        flink, blink, kind, height, num = be('IIbBH', nd, 0)
        offs = [be('H', nd, self.node_size - 2 * (i + 1))[0] for i in range(num + 1)]
        return flink, kind, [nd[offs[i]:offs[i + 1]] for i in range(num)]

    def records(self):
        n = self.first_leaf
        while n:
            flink, kind, rs = self.recs(self.node(n))
            for r in rs:
                klen, = be('H', r, 0)
                k = r[:2 + klen]
                rest = r[2 + klen:]
                if len(k) % 2:
                    pass
                yield k, rest
            n = flink


def cat_key(parent, name):
    u = name.encode('utf-16-be')
    return parent, u


def fold(u):
    return u.decode('utf-16-be')


class Catalog:
    """Path lookup by descending the catalog B-tree."""

    def __init__(self, fs):
        self.fs, self.bt = fs, fs.cat

    def cmp(self, a, b):
        (pa, na), (pb, nb) = a, b
        if pa != pb:
            return -1 if pa < pb else 1
        if self.fs.hfsx:
            x, y = na, nb   # binary compare (HFSX case sensitive)
        else:
            x, y = na.lower(), nb.lower()
        return (x > y) - (x < y)

    def parse_key(self, r):
        klen, parent, nlen = be('HIH', r, 0)
        name = r[8:8 + 2 * nlen].decode('utf-16-be', 'replace')
        return (parent, name), r[2 + klen:]

    def find(self, parent, name):
        want = (parent, name)
        n = self.bt.root
        while True:
            nd = self.bt.node(n)
            flink, kind, rs = self.bt.recs(nd)
            if kind == -1:  # leaf
                for r in rs:
                    k, data = self.parse_key(r)
                    if self.cmp(k, want) == 0:
                        return data
                return None
            # index: last key <= want
            child = None
            for r in rs:
                k, data = self.parse_key(r)
                if self.cmp(k, want) <= 0:
                    child, = be('I', data, 0)
                else:
                    break
            if child is None:
                return None
            n = child

    def children(self, parent):
        out = []
        n = self.bt.root
        # descend to the leaf that holds (parent, "")
        want = (parent, '')
        while True:
            flink, kind, rs = self.bt.recs(self.bt.node(n))
            if kind == -1:
                break
            child = None
            for r in rs:
                k, data = self.parse_key(r)
                if self.cmp(k, want) <= 0:
                    child, = be('I', data, 0)
                else:
                    break
            n = child if child is not None else be('I', self.parse_key(rs[0])[1], 0)[0]
        while n:
            flink, kind, rs = self.bt.recs(self.bt.node(n))
            for r in rs:
                (p, name), data = self.parse_key(r)
                if p > parent:
                    return out
                if p == parent and name:
                    out.append((name, data))
            n = flink
        return out

    private = None

    def resolve_link(self, rec):
        """A file hard link (fdType 'hlnk', creator 'hfs+'): the iNode<special> file of the private folder."""
        if rec is None or be('h', rec, 0)[0] != 2 or rec[48:56] != b'hlnkhfs+':
            return rec
        if self.private is None:
            for name, data in self.children(2):
                if name.endswith('HFS+ Private Data') and be('h', data, 0)[0] == 1:
                    self.private, = be('I', data, 8)
        inode, = be('I', rec, 44)
        target = self.find(self.private, f'iNode{inode}')
        return target if target is not None else rec

    def lookup(self, path):
        cnid = 2
        rec = None
        for part in [p for p in path.split('/') if p]:
            rec = self.resolve_link(self.find(cnid, part))
            if rec is None:
                raise FileNotFoundError(path)
            rtype, = be('h', rec, 0)
            if rtype == 1:      # folder
                cnid, = be('I', rec, 8)
            elif rtype == 2:    # file
                cnid, = be('I', rec, 8)
            else:
                raise ValueError(f'record type {rtype}')
        return cnid, rec


def file_info(rec):
    rtype, flags = be('hH', rec, 0)
    cnid, = be('I', rec, 8)
    mode, = be('H', rec, 32 + 10)
    data_fork = (be('Q', rec, 88)[0], [e for e in (be('II', rec, 88 + 16 + 8 * i) for i in range(8)) if e[1]])
    return cnid, mode, data_fork


def main():
    cmd, path = sys.argv[1], sys.argv[2]
    fs = HFS(Dev())
    cat = Catalog(fs)
    cnid, rec = cat.lookup(path)
    rtype = be('h', rec, 0)[0] if rec is not None else 1
    if cmd == 'ls':
        for name, data in cat.children(cnid):
            t, = be('h', data, 0)
            if t == 2:
                c, m, fk = file_info(data)
                print(f'f {fk[0]:12d} {name}')
            elif t == 1:
                print(f'd {"":12} {name}/')
    elif cmd == 'stat':
        if rtype == 2:
            c, m, fk = file_info(rec)
            print('file', c, oct(m), fk[0], 'bytes', len(fk[1]), 'extents')
            print('owner flags', hex(rec[41]), 'special', be('I', rec, 44)[0], 'type/creator', rec[64:72],
                  'rsrc size', be('Q', rec, 168)[0])
        else:
            print('folder', cnid)
    elif cmd == 'get':
        c, m, (size, exts) = file_info(rec)
        exts = fs.all_extents(exts, c, 0)
        with open(sys.argv[3], 'wb') as fh:
            left = size
            for start, count in exts:
                take = min(count * fs.bs, left)
                fs.d.read_big(start * fs.bs, take, fh)
                left -= take
                if left <= 0:
                    break
        print('wrote', size, 'bytes from', len(exts), 'extents')


if __name__ == '__main__':
    main()
