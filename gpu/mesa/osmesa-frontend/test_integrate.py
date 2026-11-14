#!/usr/bin/env python3
"""Pruebas de integrate.py con un árbol de Mesa SINTÉTICO (los textos ancla mínimos). No necesita Mesa. python3 -I gpu/mesa/osmesa-frontend/test_integrate.py"""
import os, sys, shutil, subprocess, tempfile, unittest
HERE = os.path.dirname(os.path.abspath(__file__)); INT = os.path.join(HERE, 'integrate.py')
FILES = {
    'meson.options': "option(\n  'glx-direct',\n  type : 'boolean',\n  value : true,\n)\n",
    'meson.build': "project('mesa')\nwith_glx_direct = get_option('glx-direct')\nif dep_unwind.found()\n  pre_args += '-DHAVE_LIBUNWIND'\nendif\n",
    'src/gallium/meson.build': "if with_dri\n  subdir('frontends/dri')\n  subdir('targets/dri')\nendif\n",
    'include/meson.build': "if with_dri\n  install_headers('GL/internal/dri_interface.h', subdir : 'GL/internal')\nendif\n",
}


def run(mesa): return subprocess.run([sys.executable, '-I', INT, mesa], capture_output=True, text=True)


class T(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='mesa-fake.')
        for rel, text in FILES.items():
            p = os.path.join(self.d, rel); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(text)
    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)
    def rd(self, rel): return open(os.path.join(self.d, rel)).read()

    def test_applies_once_and_places_the_sources(self):
        r = run(self.d); self.assertEqual(r.returncode, 0, r.stderr + r.stdout)
        for rel in ('src/gallium/frontends/osmesa/osmesa.c', 'src/gallium/frontends/osmesa/meson.build', 'src/gallium/targets/osmesa/osmesa_target.c', 'src/gallium/targets/osmesa/meson.build', 'include/GL/osmesa.h'):
            self.assertTrue(os.path.isfile(os.path.join(self.d, rel)), rel)
        self.assertIn("with_osmesa = get_option('osmesa')", self.rd('meson.build')); self.assertIn("option(\n  'osmesa',", self.rd('meson.options'))
        self.assertIn("subdir('frontends/osmesa')", self.rd('src/gallium/meson.build')); self.assertIn("install_headers('GL/osmesa.h'", self.rd('include/meson.build'))

    def test_the_postprocess_patch_is_applied_and_osmesa_c_no_longer_includes_it(self):
        run(self.d); c = self.rd('src/gallium/frontends/osmesa/osmesa.c')
        self.assertNotIn('postprocess/filters.h', c); self.assertNotIn('pp_run(', c); self.assertIn('OSMesaPostprocess', c)           # el símbolo se conserva

    def test_a_second_run_fails_loudly_instead_of_duplicating(self):
        self.assertEqual(run(self.d).returncode, 0); r = run(self.d); self.assertNotEqual(r.returncode, 0); self.assertIn('ya integrado', r.stderr)

    def test_a_missing_anchor_fails_loudly(self):
        open(os.path.join(self.d, 'src/gallium/meson.build'), 'w').write("if with_other\nendif\n"); r = run(self.d); self.assertNotEqual(r.returncode, 0); self.assertIn('aparece 0 veces', r.stderr)

    def test_not_a_mesa_tree_is_refused(self):
        e = tempfile.mkdtemp(); r = run(e); shutil.rmtree(e); self.assertNotEqual(r.returncode, 0)

    def test_pristine_sources_match_their_recorded_hashes(self):
        import hashlib
        for line in open(os.path.join(HERE, 'SOURCES.sha256')).read().splitlines():
            h, n = line.split(); self.assertEqual(hashlib.sha256(open(os.path.join(HERE, n), 'rb').read()).hexdigest(), h, n)

    def test_a_modified_source_is_detected(self):
        shutil.copytree(HERE, self.d + '/copy'); open(self.d + '/copy/osmesa.c', 'a').write('\n/* x */\n')
        r = subprocess.run([sys.executable, '-I', self.d + '/copy/integrate.py', self.d], capture_output=True, text=True); self.assertNotEqual(r.returncode, 0); self.assertIn('fuente modificada', r.stderr)


if __name__ == '__main__':
    unittest.main()
