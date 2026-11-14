#!/usr/bin/env python3
"""integrate.py MESA_DIR: reinjerta el frontend OSMesa (eliminado de Mesa en 25.1) en un árbol de Mesa 26.x. D-0031/D-0032 (opción B2).

  python3 -I gpu/mesa/osmesa-frontend/integrate.py MESA_DIR

Copia osmesa.c, osmesa_target.c, osmesa.sym, osmesa.def.in (MIT, de Mesa 25.0.7, sin cambios; SOURCES.sha256) y osmesa.h, pone los Meson de ./meson/ y hace
las ediciones mínimas de los Meson de Mesa. Como patch-mesa.py, CADA edición exige que el texto aparezca EXACTAMENTE UNA VEZ: un cambio de Mesa falla en alto.
Después ejecutar gpu/mesa/patch-mesa.py (la parte de Panfrost; sus rutas han cambiado en 26.x: ver docs/S7GE_OSMESA_MESA26_COMPATIBILITY.md)."""
import hashlib, shutil, subprocess, sys
from pathlib import Path

here = Path(__file__).resolve().parent
mesa = Path(sys.argv[1]) if len(sys.argv) == 2 else sys.exit(__doc__)
if not (mesa / 'meson.build').is_file(): sys.exit('no parece un árbol de Mesa: %s' % mesa)
if (mesa / 'src/gallium/frontends/osmesa').exists() or 'with_osmesa' in (mesa / 'meson.build').read_text():
    sys.exit('el árbol ya integrado: contiene OSMesa (frontends/osmesa o with_osmesa); use un árbol limpio de Mesa')
for line in (here / 'SOURCES.sha256').read_text().splitlines():          # las fuentes copiadas de Mesa 25.0.7 no han cambiado
    digest, name = line.split(); assert hashlib.sha256((here / name).read_bytes()).hexdigest() == digest, 'fuente modificada: ' + name


def edit(rel, old, new):
    path = mesa / rel; text = path.read_text()
    assert text.count(old) == 1, f'{rel}: el texto esperado aparece {text.count(old)} veces:\n{old}'
    path.write_text(text.replace(old, new)); print('editado ', rel)


def put(src, rel):
    dst = mesa / rel; dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(here / src, dst); print('copiado ', rel)


put('osmesa.c', 'src/gallium/frontends/osmesa/osmesa.c'); put('meson/frontend.build', 'src/gallium/frontends/osmesa/meson.build')
put('osmesa_target.c', 'src/gallium/targets/osmesa/osmesa_target.c'); put('osmesa.sym', 'src/gallium/targets/osmesa/osmesa.sym')
put('osmesa.def.in', 'src/gallium/targets/osmesa/osmesa.def.in'); put('meson/target.build', 'src/gallium/targets/osmesa/meson.build'); put('osmesa.h', 'include/GL/osmesa.h')
for pf in sorted((here / 'patches').glob('*.patch')):                      # correcciones propias sobre osmesa.c (nuestro fork, política en docs/S7GE_OSMESA_FORK_POLICY.md)
    r = subprocess.run(['patch', '-p1', '--no-backup-if-mismatch', '-d', str(mesa / 'src/gallium/frontends/osmesa'), '-i', str(pf)], capture_output=True, text=True)
    assert r.returncode == 0, f'no aplica {pf.name}: {r.stdout}{r.stderr}'; print('parche  ', pf.name)
edit('meson.options', "option(\n  'glx-direct',", "option(\n  'osmesa',\n  type : 'boolean',\n  value : false,\n  description : 'Build OSMesa (Galaxy S7 port: frontend kept by gpu/mesa/osmesa-frontend)',\n)\n\noption(\n  'glx-direct',")
edit('meson.build', "with_glx_direct = get_option('glx-direct')\n", "with_glx_direct = get_option('glx-direct')\nwith_osmesa = get_option('osmesa')\n")
edit('meson.build', "if dep_unwind.found()\n  pre_args += '-DHAVE_LIBUNWIND'\nendif\n",
     "if dep_unwind.found()\n  pre_args += '-DHAVE_LIBUNWIND'\nendif\n\nif with_osmesa\n  if not with_gallium_swrast\n    error('OSMesa gallium requires gallium softpipe or llvmpipe.')\n  endif\n  if host_machine.system() == 'windows'\n    osmesa_lib_name = 'osmesa'\n  else\n    osmesa_lib_name = 'OSMesa'\n  endif\nendif\n")
edit('src/gallium/meson.build', "if with_dri\n  subdir('frontends/dri')\n  subdir('targets/dri')\nendif\n", "if with_dri\n  subdir('frontends/dri')\n  subdir('targets/dri')\nendif\nif with_osmesa\n  subdir('frontends/osmesa')\n  subdir('targets/osmesa')\nendif\n")
edit('include/meson.build', "if with_dri\n  install_headers('GL/internal/dri_interface.h', subdir : 'GL/internal')\nendif\n", "if with_osmesa\n  install_headers('GL/osmesa.h', subdir : 'GL')\nendif\n\nif with_dri\n  install_headers('GL/internal/dri_interface.h', subdir : 'GL/internal')\nendif\n")
print('listo: configurar con -Dosmesa=true -Dgallium-drivers=softpipe (o panfrost,softpipe)')
