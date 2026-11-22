#!/usr/bin/env python3
"""herolte-diag-patch-check.py PATCH... : ¿tocan los parches SOLO ficheros de diagnóstico de arranque temprano?

Respalda la autorización amplia de diagnóstico (D-0043): un kernel solo entra si todos los parches nuevos o cambiados
desde el último kernel aprobado tocan únicamente ficheros de esta lista blanca (arranque temprano: dibujo en pantalla,
marcas, boot-arg herostop, contadores) o, en los ficheros HOOK_ONLY (D-0045), solo añaden enganches de dibujo. No juzga el CONTENIDO de los cambios: eso lo revisa y registra el ingeniero.
Salida 0 = todos dentro de la lista; 1 = algún parche toca otro fichero (se imprime cuál); 2 = uso incorrecto.
"""
import sys, re
ALLOWED = {
    'osfmk/arm/arm_init.c',
    'osfmk/arm64/arm_vm_init.c',
    'osfmk/arm64/start.s',
    'osfmk/arm64/sweet_early.c',
    'osfmk/arm64/sweet_early.h',
}
# D-0045: ficheros del camino de arranque donde SOLO se admite enganchar el dibujo: cada línea añadida debe ser una llamada a
# sweet_early_*, una declaración extern de ellas, o una directiva #if/#endif sobre A5XELTE, o estar en blanco.
HOOK_ONLY = {
    'bsd/kern/kdebug.c',
    'osfmk/kern/startup.c',
    'osfmk/arm/model_dep.c',
    'osfmk/arm64/machine_routines.c',
    'osfmk/vm/vm_init.c',
    'pexpert/arm/pe_kprintf.c',
    'osfmk/kern/printf.c',
}
HOOK_OK = re.compile(r'^\s*(sweet_early_[a-z_]+\([^;]*\);|extern void sweet_early_[a-z_]+\([^;]*\);|#if defined\(A5XELTE\)|#endif|#else.*|)\s*$')
def hook_violations(path):
    bad, cur = [], None
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^\+\+\+ b/(\S+)', line)
        if m: cur = m.group(1); continue
        if cur in HOOK_ONLY and line.startswith('+') and not line.startswith('+++'):
            if not HOOK_OK.match(line[1:].rstrip('\n')): bad.append((cur, line[1:].rstrip()))
    return bad
def files(path):
    out = []
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'^\+\+\+ b/(\S+)', line)
        if m: out.append(m.group(1))
    return out
def main(argv):
    if len(argv) < 2: print(__doc__); return 2
    bad = 0
    for p in argv[1:]:
        fs = files(p)
        if not fs: print('FALLA  %s: no se encontraron ficheros (¿parche vacío?)' % p); bad += 1; continue
        extra = [f for f in fs if f not in ALLOWED and f not in HOOK_ONLY]
        hv = hook_violations(p)
        if extra: print('FALLA  %s toca fuera de la lista blanca: %s' % (p, ', '.join(extra))); bad += 1
        elif hv: print('FALLA  %s: líneas añadidas que no son solo un enganche de dibujo: %s' % (p, '; '.join('%s: %s' % x for x in hv))); bad += 1
        else: print('OK     %s: %s' % (p, ', '.join(fs)))
    return 1 if bad else 0
if __name__ == '__main__': sys.exit(main(sys.argv))
