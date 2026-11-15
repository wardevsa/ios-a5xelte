#!/usr/bin/env python3
"""Summarise a herolte persistent log (tools/herolte-log-pull.py output) in one screen.

  herolte-log-report.py LOG.txt

Read-only. Prints: how long the system lived, memory, frame statistics, CPU/GPU clocks, temperatures,
DROP and hero-run lines, crashes, abnormal exits and the shutdown reason. The log may hold device
identifiers: the report prints no serial numbers and the log must stay out of git.
"""
import re
import sys
from collections import Counter


def fnum(text, default=0.0):
    try:
        return float(text)
    except ValueError:
        return default


def summarise(lines):
    out = []
    alive = [int(m.group(1)) for m in (re.match(r'HEROLTE LOG: alive (\d+) s', l) for l in lines) if m]
    free = [int(m.group(1)) for m in (re.search(r'MB free (\d+)', l) for l in lines
                                       if l.startswith('HEROLTE LOG: alive')) if m]
    out.append('vida: %s s (%d latidos)' % (alive[-1] if alive else '?', len(alive)))
    if free:
        out.append('memoria libre MB: min %d, última %d' % (min(free), free[-1]))

    fps, copy, copymax = [], [], []
    for l in lines:
        m = re.search(r'A5XELTE FB: frames=\d+ .*fps=([0-9.]+).*avg_copy_us=(\d+) max_copy_us=(\d+)', l)
        if m:
            fps.append(fnum(m.group(1)))
            copy.append(int(m.group(2)))
            copymax.append(int(m.group(3)))
    if fps:
        out.append('cuadros: %d muestras, fps medio %.1f, máx %.1f, copia media %d us, máx %d us' % (
            len(fps), sum(fps) / len(fps), max(fps), sum(copy) // len(copy), max(copymax)))
    present = [l for l in lines if l.startswith('HEROLTE GPU PRESENT:')]
    if present:
        out.append('GPU presenta: %d líneas; última: %s' % (len(present), present[-1][:100]))

    for pat, label in ((r'HEROLTE CPU: Mongoose at (\d+) MHz', 'Mongoose'),
                       (r'HEROLTE GPU: clock: .*-> (\d+) MHz', 'GPU')):
        hits = [m.group(1) for m in (re.search(pat, l) for l in lines) if m]
        if hits:
            out.append('%s: %s MHz' % (label, hits[-1]))
    soc = [int(m.group(1)) for m in (re.search(r'HEROLTE POWER: SoC (\d+) C', l) for l in lines) if m]
    if soc:
        out.append('SoC C: máx %d, última %d (%d lecturas)' % (max(soc), soc[-1], len(soc)))
    for l in lines:
        if l.startswith('SWEET BATTERY:'):
            last_batt = l
    if any(l.startswith('SWEET BATTERY:') for l in lines):
        out.append(last_batt[:100])

    drop = [l for l in lines if 'HEROLTE DROP' in l or 'F_FULLFSYNC' in l or 'cache flush' in l]
    out.append('DROP: ' + ('; '.join(d[:90] for d in drop[:4]) if drop else 'sin líneas'))
    hero = [l for l in lines if 'hero-run:' in l]
    gl = [l for l in lines if l.startswith('HEROLTE GL:')]
    out.append('GL en backboardd: ' + ('; '.join(g[:100] for g in gl[:3]) if gl else 'sin líneas HEROLTE GL'))
    out.append('hero-run: %d líneas' % len(hero))
    out.extend('  ' + h[:130] for h in hero[:12])

    crashes = Counter(re.match(r'CRASH (\w+)', l).group(1) for l in lines if re.match(r'CRASH \w+\[', l))
    if crashes:
        out.append('crashes: ' + ', '.join('%s x%d' % kv for kv in crashes.most_common(8)))
    exits = Counter(re.sub(r'\[\d+\]', '', l.split(' xstat ')[0]).replace('EXIT ', '')
                    + ' xstat ' + l.split(' xstat ')[1].strip()
                    for l in lines if l.startswith('EXIT ') and ' xstat ' in l and not l.endswith(' xstat 0'))
    if exits:
        out.append('salidas anormales: ' + '; '.join('%s x%d' % kv for kv in exits.most_common(6)))
    spawn = Counter(re.sub(r'\[\d+\]', '', l)[:80] for l in lines if l.startswith('SPAWN FAILED'))
    if spawn:
        out.append('SPAWN FAILED: %d (%d distintos)' % (sum(spawn.values()), len(spawn)))

    nz = []
    for l in lines:
        m = re.match(r'FBSRC \d+ pass (\d) .* nz_rgb (\d+)', l)
        if m and int(m.group(2)) > 0:
            nz.append(int(m.group(2)))
    out.append('sondas FBSRC con contenido: %d' % len(nz))
    for l in lines:
        if 'initiated by' in l:
            out.append('apagado: ' + l[-90:])
            break
    pan = [l for l in lines if re.search(r'panic|PANIC', l)]
    out.append('pánico: ' + (pan[0][:100] if pan else 'ninguno en el log'))
    return out


def main(argv):
    if len(argv) != 2:
        print(__doc__)
        return 2
    with open(argv[1], encoding='utf-8', errors='replace') as f:
        lines = f.read().split('\n')
    print('\n'.join(summarise(lines)))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
