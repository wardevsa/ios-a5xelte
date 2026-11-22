#!/usr/bin/env python3
"""Adapt a Mesa 25.0.x tree for Panfrost-in-OSMesa on the Galaxy S7's iOS.

  patch-mesa.py MESA_DIR

Every edit asserts that the text it replaces is found exactly once, so a
Mesa change shows up as a clear failure here rather than a silent no-op.
Also copies hero_hw.c into the OSMesa target.
"""
import shutil
import sys
from pathlib import Path

mesa = Path(sys.argv[1])
here = Path(__file__).resolve().parent


def edit(rel, old, new):
    path = mesa / rel
    text = path.read_text()
    assert text.count(old) == 1, f'{rel}: expected text found {text.count(old)} times:\n{old}'
    path.write_text(text.replace(old, new))
    print('patched', rel)


# libdrm (our stand-in) on Darwin when Panfrost is built: Mesa only looks
# for it on systems with KMS.
edit('meson.build',
     "with_gallium_drisw_kms = false\nif system_has_kms_drm\n",
     "with_gallium_drisw_kms = false\n"
     "if system_has_kms_drm or (host_machine.system() == 'darwin' and with_gallium_panfrost)\n")

# BO mappings come from the HeroGPU user client, not mmap() on the DRM fd.
edit('src/panfrost/lib/kmod/pan_kmod.h',
     "static inline void *\npan_kmod_bo_mmap(",
     "#ifdef __APPLE__\n"
     "void *herodrm_mmap(void *addr, size_t size, int prot, int flags, int fd, off_t offset);\n"
     "#endif\n\n"
     "static inline void *\npan_kmod_bo_mmap(")
edit('src/panfrost/lib/kmod/pan_kmod.h',
     "   host_addr = os_mmap(host_addr, size, prot, flags, bo->dev->fd,\n",
     "#ifdef __APPLE__\n"
     "   host_addr = herodrm_mmap(host_addr, size, prot, flags, bo->dev->fd,\n"
     "                            mmap_offset + bo_offset);\n"
     "#else\n"
     "   host_addr = os_mmap(host_addr, size, prot, flags, bo->dev->fd,\n")
edit('src/panfrost/lib/kmod/pan_kmod.h',
     "                       mmap_offset + bo_offset);\n   if (host_addr == MAP_FAILED) {",
     "                       mmap_offset + bo_offset);\n#endif\n   if (host_addr == MAP_FAILED) {")

# Imported IOSurfaces (herodrm_surface_import) are stand-in descriptors, not
# dma-bufs: their size comes from the libdrm stand-in.
edit('src/panfrost/lib/kmod/pan_kmod.c',
     "      size_t size = lseek(fd, 0, SEEK_END);\n",
     "#ifdef __APPLE__\n"
     "      extern int64_t herodrm_prime_size(int fd);\n"
     "      size_t size = (size_t)herodrm_prime_size(fd);\n"
     "#else\n"
     "      size_t size = lseek(fd, 0, SEEK_END);\n"
     "#endif\n")

edit('src/gallium/drivers/panfrost/pan_bo.c',
     "   if (os_munmap((void *)(uintptr_t)bo->ptr.cpu, panfrost_bo_size(bo))) {",
     "#ifdef __APPLE__\n"
     "   int herodrm_munmap(void *addr, size_t size);\n"
     "   if (herodrm_munmap((void *)(uintptr_t)bo->ptr.cpu, panfrost_bo_size(bo))) {\n"
     "#else\n"
     "   if (os_munmap((void *)(uintptr_t)bo->ptr.cpu, panfrost_bo_size(bo))) {\n"
     "#endif")

# OSMesa: the GPU screen first, softpipe when it is unavailable.
edit('src/gallium/targets/osmesa/osmesa_target.c',
     "struct pipe_screen *\nosmesa_create_screen(void)\n{\n",
     "struct pipe_screen *hero_hw_create_screen(void) __attribute__((weak));\n\n"
     "struct pipe_screen *\nosmesa_create_screen(void)\n{\n"
     "   if (hero_hw_create_screen) {\n"
     "      struct pipe_screen *hw = hero_hw_create_screen();\n"
     "      if (hw)\n"
     "         return debug_screen_wrap(hw);\n"
     "   }\n\n")
edit('src/gallium/targets/osmesa/meson.build',
     "libosmesa = shared_library(\n  osmesa_lib_name,\n  'osmesa_target.c',\n",
     "osmesa_hero_files = []\n"
     "osmesa_hero_deps = []\n"
     "if host_machine.system() == 'darwin' and with_gallium_panfrost\n"
     "  osmesa_hero_files += 'hero_hw.c'\n"
     "  osmesa_hero_deps += [driver_panfrost, dep_libdrm, idep_xmlconfig]\n"
     "endif\n\n"
     "libosmesa = shared_library(\n  osmesa_lib_name,\n  'osmesa_target.c', osmesa_hero_files,\n")
edit('src/gallium/targets/osmesa/meson.build',
     "    dep_ws2_32, dep_thread, dep_clock, dep_unwind, driver_swrast, idep_mesautil,\n",
     "    dep_ws2_32, dep_thread, dep_clock, dep_unwind, driver_swrast, idep_mesautil,\n"
     "    osmesa_hero_deps,\n")

# OpenGL ES contexts from OSMesa (profile 0x36), for the EAGL shim that
# CoreAnimation's GLES renderer runs on (gpu/eagl). From Bergamota's
# gpu/eagl/mesa patch (MIT).
edit('src/gallium/frontends/osmesa/osmesa.c',
     "             profile != OSMESA_COMPAT_PROFILE)\n            return NULL;",
     "             profile != OSMESA_COMPAT_PROFILE &&\n"
     "             profile != 0x36 /* OpenGL ES profile */)\n            return NULL;")
edit('src/gallium/frontends/osmesa/osmesa.c',
     "      ? API_OPENGL_CORE : API_OPENGL_COMPAT;\n",
     "      ? API_OPENGL_CORE : API_OPENGL_COMPAT;\n"
     "   if (profile == 0x36) /* GLES context: major 1 = ES1, else ES2/ES3 */\n"
     "      attribs.profile = (version_major == 1) ? API_OPENGLES : API_OPENGLES2;\n")

# The OSMesaSweet* entry points the EAGL shim uses (GPU blit into IOSurfaces).
osmesa_c = mesa / 'src/gallium/frontends/osmesa/osmesa.c'
osmesa_c.write_text(osmesa_c.read_text() + '\n' + (here / 'osmesa_hero.inc').read_text())
print('appended osmesa_hero.inc')

shutil.copy(here / 'hero_hw.c', mesa / 'src/gallium/targets/osmesa/hero_hw.c')
print('copied hero_hw.c')
