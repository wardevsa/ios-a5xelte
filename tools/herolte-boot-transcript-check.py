#!/usr/bin/env python3
"""herolte-boot-transcript-check.py: clasifica la TRANSCRIPCIÓN (texto escrito a mano desde el vídeo/foto de la pantalla) del primer arranque
frente a docs/S7GE_BOOT_LOG_EXPECTATIONS.md y docs/S7GE_MIN_BOOT_VALIDATION.md. NO lee el teléfono ni ningún log: con `herolog=0` no hay log persistente.

  python3 -I tools/herolte-boot-transcript-check.py TRANSCRIPCION.txt [--min]      # --min: la variante mínima (herowifi=0 heropower=0 herogpu=0)

Salida: el resultado A-E de S7GE_MIN_BOOT_VALIDATION.md, las etapas vistas, los prefijos PROHIBIDOS que aparecieron y la última línea. Es una AYUDA para no
interpretar a ojo; no prueba nada por sí sola. Códigos de salida: 0 = A (N2 completo), 1 = B/C/D/E, 2 = uso incorrecto."""
import re, sys

LOADER_FAIL = ('ENTRY OUTSIDE KERNEL', 'BAD SWEETXNU PAYLOAD', 'PAYLOAD OVERLAPS XNU RAM')
STAGES = [('loader', 'HEROLTE XNU LOADER'), ('entry', 'ENTRY'), ('bootargs', 'BOOTARGS'), ('jump', 'JUMP TO XNU'), ('xnu_entry', 'XNU ENTRY'),
          ('mmu_on', 'XNU MMU ON'), ('kernel', 'Darwin Kernel Version'), ('root_fail', 'cannot mount root')]
FORBIDDEN_MIN = ('HEROLTE WIFI', 'HEROLTE GPU', 'HEROLTE CPU', 'HEROLTE POWER', 'HEROLTE TMU', 'HEROLTE DROP')


def classify(text, minimal=False):
    low = text.lower()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    seen = [name for name, pat in STAGES if pat.lower() in low]
    forbidden = sorted({p for p in FORBIDDEN_MIN if minimal and p.lower() in low})
    fail = [m for m in LOADER_FAIL if m.lower() in low or 'loader fail' in low and m.lower() in low]
    res = {'etapas': seen, 'prohibidos': forbidden, 'ultima_linea': lines[-1] if lines else '', 'lineas': len(lines)}
    if not lines: res['resultado'] = 'D'; res['motivo'] = 'transcripción vacía: pantalla negra / sin texto'
    elif 'loader fail' in low or fail: res['resultado'] = 'C'; res['motivo'] = 'el cargador falló: ' + (', '.join(fail) or 'LOADER FAIL')
    elif 'reboot' in low and low.count('reboot') >= 3 or 'bucle' in low: res['resultado'] = 'E'; res['motivo'] = 'reinicios repetidos anotados'
    elif 'root_fail' in seen or ('kernel' in seen and 'cpus' in low and 'mount' in low): res['resultado'] = 'A'; res['motivo'] = 'llegó a la consola del kernel y falló al montar la raíz (esperado en N2)'
    elif 'panic' in low or any(s in seen for s in ('xnu_entry', 'mmu_on', 'kernel')): res['resultado'] = 'B'; res['motivo'] = 'N2 parcial: última etapa vista ' + (seen[-1] if seen else '?')
    else: res['resultado'] = 'D'; res['motivo'] = 'no se reconoce ninguna etapa del kernel'
    return res


def main(argv):
    args = [a for a in argv[1:] if a != '--min']
    if len(args) != 1: print(__doc__); return 2
    r = classify(open(args[0], encoding='utf-8', errors='replace').read(), minimal='--min' in argv)
    print('RESULTADO %s: %s' % (r['resultado'], r['motivo'])); print('etapas vistas: %s' % (', '.join(r['etapas']) or 'ninguna')); print('última línea: %s' % (r['ultima_linea'] or '—'))
    if r['prohibidos']: print('ATENCIÓN: aparecieron prefijos que la variante mínima NO debe imprimir: %s (la línea de arranque efectiva no es la prevista; anotarlo)' % ', '.join(r['prohibidos']))
    return 0 if r['resultado'] == 'A' else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
