# gpu/mesa/osmesa-frontend: el frontend OSMesa que Mesa eliminó (D-0031, D-0032: opción B2)

Mesa **eliminó OSMesa en la versión 25.1.0**. El proyecto lo necesita (la ruta de OpenGL ES es OSMesa + Panfrost sobre `HeroGPU`), así que **mantenemos el frontend nosotros** y lo reinyectamos en un Mesa más nuevo. Política: `docs/S7GE_OSMESA_FORK_POLICY.md`. Compatibilidad medida: `docs/S7GE_OSMESA_MESA26_COMPATIBILITY.md`.

| Fichero | Origen | Cambios |
|---|---|---|
| `osmesa.c`, `osmesa_target.c`, `osmesa.sym`, `osmesa.def.in`, `osmesa.h` | **Mesa 25.0.7** (commit `742a20f48c59e8649533c84c4d49dd95b403f5da`), licencia **MIT**, cabeceras originales intactas | **ninguno** (hashes en `SOURCES.sha256`; `integrate.py` los comprueba) |
| `patches/0001-osmesa-no-postprocess.patch` | propio | quita el uso del módulo `postprocess`, que Mesa también eliminó; `OSMesaPostprocess()` se conserva y avisa |
| `meson/frontend.build`, `meson/target.build` | Meson de 25.0.7 | adaptados a 26.x (sin `with_shared_glapi` ni `libglapi_static`; `glapi.h` está ahora en `src/mesa/glapi/glapi/`) |
| `integrate.py` | propio | copia, parchea y edita los Meson de Mesa; **cada edición exige que el texto aparezca exactamente una vez** (como `gpu/mesa/patch-mesa.py`): un cambio de Mesa falla en alto |
| `test_integrate.py` | propio | pruebas con un árbol de Mesa sintético |

## Uso
```
python3 -I gpu/mesa/osmesa-frontend/integrate.py MESA_DIR        # MESA_DIR = árbol de Mesa 26.x (p. ej. el tag mesa-26.2.4)
meson setup build -Dosmesa=true -Dgallium-drivers=softpipe ...   # (o panfrost,softpipe)
ninja -C build src/gallium/targets/osmesa/libOSMesa.so.8.0.0
```
Después, `gpu/mesa/patch-mesa.py` (la parte de Panfrost): **hoy 2 de sus 12 ediciones no aplican a 26.2.4** (`pan_kmod.h`, el gancho de `mmap`); ver el documento de compatibilidad. `gpu/mesa/build-mesa.sh` **no se ha cambiado** y sigue compilando Mesa 25.0.7.

## Estado (2026-11-14)
Compila y enlaza con Mesa 26.2.4 en **Linux** (softpipe, sin LLVM) y una prueba mínima crea un contexto, limpia a rojo y lee el píxel correcto (`GL 3.3 compatibility, Mesa 26.2.4, softpipe`). **No** se ha compilado para iOS/Darwin ni con Panfrost ni se ha probado en el teléfono.
