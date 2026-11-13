#!/usr/bin/env python3
"""Tests of tools/governance.py. The real governance data must pass; every rule must also FAIL when its condition is broken (negative tests on temporary copies).
    python3 -W ignore tools/test_governance.py"""
import importlib.util, os, re, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location('gov', os.path.join(HERE, 'governance.py'))
gov = importlib.util.module_from_spec(spec); spec.loader.exec_module(gov)
TOOL = os.path.join(HERE, 'governance.py')


def run(root, *args):
    return subprocess.run([sys.executable, '-I', TOOL, '--root', root, '--no-git', *args], capture_output=True, text=True)


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='gov-test.')
        shutil.copytree(os.path.join(REPO, 'governance'), os.path.join(self.d, 'governance'), ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy(os.path.join(REPO, 'AGENTS.md'), self.d)

    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)       # only this test's own temporary copy

    def path(self, *p): return os.path.join(self.d, 'governance', *p)

    def edit(self, rel, fn):
        p = self.path(*rel.split('/')); s = open(p, encoding='utf-8').read(); t = fn(s)
        self.assertNotEqual(s, t, 'the mutation changed nothing: %s' % rel); open(p, 'w', encoding='utf-8').write(t)

    def render(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()): gov.cmd_render(self.d, False)

    def errors(self, render=True):
        if render: self.render()
        return gov.check(self.d, use_git=False)[0]

    def assertErr(self, needle, render=True):
        errs = self.errors(render); self.assertTrue(any(needle in e for e in errs), (needle, errs))


class Positive(unittest.TestCase):
    def test_real_governance_is_valid(self):
        errs, warns = gov.check(REPO, use_git=True); self.assertEqual(errs, [], errs)

    def test_views_are_current(self):
        self.assertEqual(gov.cmd_render(REPO, True), 0)

    def test_there_is_a_next_autonomous_task_and_it_is_not_c_or_x(self):
        policy, tasks = gov.load(REPO, 'policy.toml'), gov.load(REPO, 'tasks.toml'); n = gov.next_task(policy, tasks)
        self.assertIsNotNone(n); self.assertIn(gov.tier_of_actions(policy, n['actions']), ('A', 'B'))

    def test_exit_codes_of_can_by_tier(self):
        for action, code in (('read-analysis', 0), ('patch-series-change', 10), ('publish', 20), ('privileged-or-mount', 20), ('device-write-boot', 20),
                             ('write-protected-partitions', 30), ('destructive-git', 30), ('no-existe', 2)):
            self.assertEqual(run(REPO, 'can', action).returncode, code, action)

    def test_cli_status_next_render_check(self):
        for a in (['status'], ['next'], ['render', '--check'], ['check']): self.assertEqual(run(REPO, *a).returncode, 0, a)


class Structure(Base):
    def test_missing_required_document(self):
        os.remove(self.path('HANDOFF.md')); self.assertErr('falta governance/HANDOFF.md', render=False)

    def test_missing_data_file(self):
        os.remove(self.path('data', 'evidence.toml')); self.assertErr('falta governance/data/evidence.toml', render=False)

    def test_invalid_toml(self):
        self.edit('data/tasks.toml', lambda s: s + '\n[[task\n'); self.assertErr('TOML inválido', render=False)

    def test_stale_generated_view(self):
        self.render(); self.edit('TASKS.md', lambda s: s.replace('# Cola de tareas', '# Cola de tareas EDITADA A MANO')); self.assertErr('TASKS.md está desactualizado', render=False)

    def test_broken_link_in_a_document(self):
        self.edit('README.md', lambda s: s + '\nVer [nada](NO_EXISTE.md)\n'); self.assertErr('enlace roto -> NO_EXISTE.md')

    def test_agents_md_must_point_to_governance(self):
        p = os.path.join(self.d, 'AGENTS.md'); s = open(p).read(); open(p, 'w').write(s.replace('governance/README.md', 'otra-cosa'))
        self.assertErr('AGENTS.md no apunta')

    def test_state_without_commit_marker(self):
        self.edit('STATE.md', lambda s: re.sub(r'<!-- state-commit: [0-9a-f]+ -->', '', s)); self.assertErr('STATE.md sin la marca')


class Tasks(Base):
    def test_two_tasks_in_progress(self):
        self.edit('data/tasks.toml', lambda s: s.replace('status = "ready"\npriority = 3', 'status = "in_progress"\npriority = 3', 1).replace('status = "ready"\npriority = 2', 'status = "in_progress"\npriority = 2', 1))
        self.assertErr('más de una tarea en curso')

    def test_dependency_on_missing_task(self):
        self.edit('data/tasks.toml', lambda s: s.replace('depends_on = ["T-0005"]', 'depends_on = ["T-9999"]', 1)); self.assertErr('depende de una tarea inexistente T-9999')

    def test_dependency_cycle(self):
        self.edit('data/tasks.toml', lambda s: s.replace('[[task]]\nid = "T-0008"', '[[task]]\nid = "T-0008"\n', 1).replace(
            'id = "T-0009"\ntitle', 'id = "T-0009"\ntitle', 1))
        self.edit('data/tasks.toml', lambda s: s.replace('depends_on = []\nactions = ["read-analysis", "docs-write", "local-commit"]\nacceptance = "Cada selector', 'depends_on = ["T-0009"]\nactions = ["read-analysis", "docs-write", "local-commit"]\nacceptance = "Cada selector', 1))
        self.edit('data/tasks.toml', lambda s: s.replace('depends_on = []\nactions = ["read-analysis", "docs-write", "host-tests", "local-commit"]\nacceptance = "Informe con qué parches', 'depends_on = ["T-0008"]\nactions = ["read-analysis", "docs-write", "host-tests", "local-commit"]\nacceptance = "Informe con qué parches', 1))
        self.assertErr('ciclo de dependencias')

    def test_unknown_action(self):
        self.edit('data/tasks.toml', lambda s: s.replace('actions = ["docs-write", "pc-implementation"', 'actions = ["inventada", "pc-implementation"', 1)); self.assertErr("acción desconocida 'inventada'")

    def test_blocked_without_reason(self):
        self.edit('data/tasks.toml', lambda s: s.replace('blocked_on = "decisión del director (D-0006 mantiene el generador sin cambios hasta entonces)"\n', '', 1)); self.assertErr('bloqueada sin blocked_on')

    def test_c_action_in_progress_without_authorization(self):
        self.edit('data/tasks.toml', lambda s: s.replace('id = "T-0007"\ntitle = "Retirar los originales de 224 sandboxes (~24 GiB) ya archivados y verificados"\nstatus = "blocked"',
                                                          'id = "T-0007"\ntitle = "Retirar los originales de 224 sandboxes (~24 GiB) ya archivados y verificados"\nstatus = "in_progress"', 1))
        self.assertErr('acción C en curso/hecha sin authorization_ref')

    def test_c_action_with_authorization_that_is_not_the_directors_approval(self):
        self.edit('data/tasks.toml', lambda s: s.replace('id = "T-0007"\ntitle = "Retirar los originales de 224 sandboxes (~24 GiB) ya archivados y verificados"\nstatus = "blocked"',
                                                          'id = "T-0007"\ntitle = "Retirar los originales de 224 sandboxes (~24 GiB) ya archivados y verificados"\nstatus = "in_progress"\nauthorization_ref = "D-0001"', 1))
        self.assertErr('no es una decisión APPROVED del director')

    def test_forbidden_action_in_a_live_task(self):
        self.edit('data/tasks.toml', lambda s: s.replace('actions = ["architecture-change"]\nblocked_on = "decisión del director o del jefe técnico"', 'actions = ["destructive-git"]\nblocked_on = "decisión del director o del jefe técnico"', 1))
        self.assertErr('contiene una acción prohibida (X)')

    def test_done_with_unfinished_dependency(self):
        self.edit('data/tasks.toml', lambda s: s.replace('id = "T-0002"\ntitle = "Auditoría Unicode HFS+ (XNU frente a Linux): causa, tabla de los 32 nombres, corrección propuesta"\nstatus = "done"\npriority = 2\nowner = "ingeniero"\ndepends_on = []',
                                                          'id = "T-0002"\ntitle = "Auditoría Unicode HFS+ (XNU frente a Linux): causa, tabla de los 32 nombres, corrección propuesta"\nstatus = "done"\npriority = 2\nowner = "ingeniero"\ndepends_on = ["T-0004"]', 1))
        self.assertErr('done con dependencia T-0004 sin terminar')

    def test_in_progress_with_unfinished_dependency(self):
        self.edit('data/tasks.toml', lambda s: s.replace('status = "ready"\npriority = 4\nowner = "ingeniero"\ndepends_on = []', 'status = "in_progress"\npriority = 4\nowner = "ingeniero"\ndepends_on = ["T-0003"]', 1))
        self.assertErr('en curso pero su dependencia T-0003 no está done')

    def test_duplicate_task_id_and_bad_status(self):
        self.edit('data/tasks.toml', lambda s: s.replace('id = "T-0019"', 'id = "T-0018"', 1)); self.assertErr('tarea duplicada T-0018')
        self.edit('data/tasks.toml', lambda s: s.replace('status = "in_review"', 'status = "casi-hecha"', 1)); self.assertErr("estado inválido 'casi-hecha'")

    def test_task_referencing_missing_evidence(self):
        self.edit('data/tasks.toml', lambda s: s.replace('evidence = ["E-0011"]', 'evidence = ["E-9999"]', 1)); self.assertErr('evidencia inexistente E-9999')

    def test_next_skips_blocked_and_c_tasks(self):
        policy, tasks = gov.load(REPO, 'policy.toml'), gov.load(REPO, 'tasks.toml')
        for t in tasks['task']: t['status'] = 'done' if t['status'] == 'ready' else t['status']
        self.assertIsNone(gov.next_task(policy, tasks))


class Decisions(Base):
    def test_engineer_cannot_approve(self):
        self.edit('data/decisions.toml', lambda s: s.replace('status = "PROPOSED"\nproposer = "ingeniero"\nrationale = "La Misión 0', 'status = "APPROVED"\nproposer = "ingeniero"\napproved_by = "ingeniero"\napproval_date = "2026-11-13"\napproval_ref = "yo"\nrationale = "La Misión 0', 1))
        errs = self.errors(); self.assertTrue(any('no puede aprobar' in e or 'no aprueba sus propias' in e for e in errs), errs)

    def test_approved_without_reference(self):
        self.edit('data/decisions.toml', lambda s: s.replace('approval_ref = "Mensaje del Director \'Recuperar espacio real', 'approval_ref_borrada = "Mensaje del Director \'Recuperar espacio real', 1)); self.assertErr('APPROVED sin approval_ref')

    def test_jefe_tecnico_cannot_approve_policy(self):
        self.edit('data/decisions.toml', lambda s: s.replace('scope = "policy"\nstatus = "APPROVED"\nproposer = "ingeniero"\napproved_by = "director"', 'scope = "policy"\nstatus = "APPROVED"\nproposer = "ingeniero"\napproved_by = "jefe-tecnico"', 1))
        self.assertErr('el rol jefe-tecnico no puede aprobar decisiones de ámbito policy')

    def test_proposed_with_an_approver_is_inconsistent(self):
        self.edit('data/decisions.toml', lambda s: s.replace('status = "PROPOSED"\nproposer = "ingeniero"\nrationale = "0300-0335', 'status = "PROPOSED"\nproposer = "ingeniero"\napproved_by = "director"\nrationale = "0300-0335', 1))
        self.assertErr('tiene aprobador pero estado PROPOSED')

    def test_duplicate_decision_and_bad_scope_and_supersedes(self):
        self.edit('data/decisions.toml', lambda s: s.replace('id = "D-0010"', 'id = "D-0009"', 1)); self.assertErr('decisión duplicada D-0009')
        self.edit('data/decisions.toml', lambda s: s.replace('scope = "operation"', 'scope = "caprichos"', 1)); self.assertErr("ámbito inválido 'caprichos'")
        self.edit('data/decisions.toml', lambda s: s.replace('id = "D-0007"', 'supersedes = ["D-4242"]\nid = "D-0007"', 1) if False else s.replace('title = "Reservar el rango de parches 0400+', 'supersedes = ["D-4242"]\ntitle = "Reservar el rango de parches 0400+', 1))
        self.assertErr('supersede una decisión inexistente D-4242')


class Evidence(Base):
    def test_immutable_without_hash(self):
        self.edit('data/evidence.toml', lambda s: re.sub(r'(id = "E-0001"(?:.|\n)*?)sha256 = "[0-9a-f]{64}"', r'\1sha256 = ""', s, count=1)); self.assertErr('evidencia inmutable sin SHA-256 válido')

    def test_malformed_hash(self):
        self.edit('data/evidence.toml', lambda s: re.sub(r'(id = "E-0002"(?:.|\n)*?)sha256 = "[0-9a-f]{64}"', r'\1sha256 = "zzz"', s, count=1)); self.assertErr('SHA-256 mal formado')

    def test_verify_detects_mismatch_and_skips_missing(self):
        f = os.path.join(self.d, 'artefacto.bin'); open(f, 'wb').write(b'contenido')
        import hashlib
        good = hashlib.sha256(b'contenido').hexdigest()
        open(self.path('data', 'evidence.toml'), 'w').write(
            '[[evidence]]\nid = "E-0001"\ntitle = "ok"\nkind = "artifact"\npath = "%s"\nlocation = "host"\ncreated = "2026-11-13"\nsha256 = "%s"\nimmutable = true\n\n' % (f, good) +
            '[[evidence]]\nid = "E-0002"\ntitle = "no existe"\nkind = "artifact"\npath = "/no/existe/aqui.bin"\nlocation = "host"\ncreated = "2026-11-13"\nsha256 = "%s"\nimmutable = true\n' % good)
        r = run(self.d, 'evidence'); self.assertEqual(r.returncode, 0, r.stdout); self.assertIn('OK   E-0001', r.stdout); self.assertIn('SKIP E-0002', r.stdout)
        open(f, 'wb').write(b'alterado'); r = run(self.d, 'evidence'); self.assertEqual(r.returncode, 1); self.assertIn('NO coincide', r.stdout)


class Policy(Base):
    def test_c_action_must_name_the_director(self):
        self.edit('data/policy.toml', lambda s: s.replace('id = "publish"\ntier = "C"\nauthorizer = "director"', 'id = "publish"\ntier = "C"\nauthorizer = "jefe-tecnico"', 1)); self.assertErr('la acción C publish debe exigir al director')

    def test_b_action_must_name_a_reviewer(self):
        self.edit('data/policy.toml', lambda s: s.replace('id = "architecture-change"\ntier = "B"\nreviewer = "jefe-tecnico"', 'id = "architecture-change"\ntier = "B"\nreviewer = "nadie"', 1)); self.assertErr('la acción B architecture-change debe nombrar revisor')

    def test_tiers_and_roles_are_required(self):
        self.edit('data/policy.toml', lambda s: s.replace('[tiers.X]', '[tiers.Z]', 1)); self.assertErr('los niveles deben ser exactamente A, B, C y X'.replace(' y X', ', X'))
        self.edit('data/policy.toml', lambda s: s.replace('[roles.ingeniero]', '[roles.becario]', 1)); self.assertErr('falta el rol ingeniero')


class Regression(Base):
    def test_regress_statuses(self):
        open(self.path('data', 'regression.toml'), 'w').write(
            '[[suite]]\nid = "pasa"\ntitle = "t"\ncommand = ["true"]\nbaseline = "ok"\n\n[[suite]]\nid = "falla"\ntitle = "t"\ncommand = ["false"]\nbaseline = "ok"\n\n'
            '[[suite]]\nid = "salta"\ntitle = "t"\ncommand = ["true"]\nrequires = ["/no/existe"]\nbaseline = "ok"\n\n'
            '[[suite]]\nid = "deuda"\ntitle = "t"\ncommand = ["false"]\nknown_failing = true\nbaseline = "ok"\n')
        r = run(self.d, 'regress'); self.assertEqual(r.returncode, 1, r.stdout)
        for want in ('PASS  pasa', 'FALLA falla', 'SKIP  salta', 'XFAIL deuda'): self.assertIn(want, r.stdout)
        r = run(self.d, 'regress', '--suite', 'pasa'); self.assertEqual(r.returncode, 0)
        self.assertIn('1 PASS, 0 FALLA, 0 SKIP', r.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=1)
