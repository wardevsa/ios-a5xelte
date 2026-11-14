#!/usr/bin/env python3
"""Tests of tools/governance.py: the real data must pass; every rule must also FAIL when its condition is broken (negative tests on temporary copies),
read-only commands must leave the whole work tree (.git included) byte-identical, and nothing may depend on absolute paths or on the main work tree.
    python3 -W ignore tools/test_governance.py"""
import contextlib, hashlib, importlib.util, io, json, os, re, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); REPO = os.path.dirname(HERE)
spec = importlib.util.spec_from_file_location('gov', os.path.join(HERE, 'governance.py'))
gov = importlib.util.module_from_spec(spec); spec.loader.exec_module(gov)
TOOL = os.path.join(HERE, 'governance.py')
OVERLAY = ['governance', 'AGENTS.md', 'tools/governance.py', 'tools/governance_mutation.py', 'tools/onboarding_drill.py', 'tools/test_governance.py', 'tools/test_onboarding.py']


def run(root, *args, env=None, cwd=None, git=False):
    e = dict(os.environ, **(env or {}))
    return subprocess.run([sys.executable, '-I', TOOL, '--root', root] + ([] if git else ['--no-git']) + list(args), capture_output=True, text=True, env=e, cwd=cwd)


def snapshot(d):
    out = {}
    for base, _, files in os.walk(d):
        for f in files:
            p = os.path.join(base, f)
            if os.path.islink(p): out[os.path.relpath(p, d)] = 'link:' + os.readlink(p); continue
            with open(p, 'rb') as fh: out[os.path.relpath(p, d)] = hashlib.sha256(fh.read()).hexdigest()
    return out


def make_clone(parent):
    """A git clone (with history, so the STATE anchor resolves) with the CURRENT work-tree files of governance overlaid. The real repository is never touched."""
    c = os.path.join(parent, 'repo')
    subprocess.run(['git', 'clone', '-q', '--shared', REPO, c], check=True, capture_output=True)
    for rel in OVERLAY:
        s, d = os.path.join(REPO, rel), os.path.join(c, rel)
        if os.path.isdir(s): shutil.rmtree(d, ignore_errors=True); shutil.copytree(s, d, ignore=shutil.ignore_patterns('__pycache__'))
        elif os.path.exists(s): shutil.copy(s, d)
    return c


def block(text, kind, ident):
    m = re.search(r'\[\[%s\]\]\n(?:(?!\[\[).)*?id = "%s"\n(?:(?!\n\[\[).)*' % (kind, re.escape(ident)), text, re.S)
    assert m, (kind, ident); return m


def mutate(path, kind, ident, key, value=None):
    """Set (value is a TOML literal) or delete (None) `key` inside the [[kind]] block with this id."""
    text = open(path, encoding='utf-8').read(); m = block(text, kind, ident); b = m.group(0)
    b2 = re.sub(r'\n%s = [^\n]*(?:\n(?![a-z_]+ = |\[\[)[^\n]*)*' % re.escape(key), '', b, count=1) if re.search(r'\n%s = ' % re.escape(key), b) else b
    if value is not None: b2 = b2.rstrip('\n') + '\n%s = %s\n' % (key, value)
    assert b2 != b or value is None and b2 == b, 'nothing changed'
    open(path, 'w', encoding='utf-8').write(text[:m.start()] + b2 + text[m.end():])


class Base(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.mkdtemp(prefix='gov-test.')
        shutil.copytree(os.path.join(REPO, 'governance'), os.path.join(self.d, 'governance'), ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copy(os.path.join(REPO, 'AGENTS.md'), self.d)
        # Las pruebas de autorización usan T-0007 como tarea ROJA SIN AUTORIZAR. T-0007 real ya se ejecutó (D-0023): en la copia temporal se
        # le devuelve el estado de fixture, para que las pruebas no dependan de cómo evolucione la cola real.
        tp = os.path.join(self.d, 'governance', 'data', 'tasks.toml')
        t0 = open(tp, encoding='utf-8').read(); open(tp, 'w', encoding='utf-8').write(t0.replace('status = "in_progress"', 'status = "ready"'))   # una tarea real en curso no debe contaminar las pruebas
        mutate(tp, 'task', 'T-0007', 'status', '"blocked"'); mutate(tp, 'task', 'T-0007', 'blocked_on', '"fixture de pruebas"')
        mutate(tp, 'task', 'T-0007', 'authorization_ref', None); mutate(tp, 'task', 'T-0007', 'requires_decisions', None); mutate(tp, 'task', 'T-0007', 'evidence', '["E-0011"]')
        # T-0016 se usa como tarea AMARILLA sin revisar y con una decisión requerida aún PROPUESTA (D-0007); la real ya se cerró: fixture en la copia.
        mutate(tp, 'task', 'T-0016', 'status', '"blocked"'); mutate(tp, 'task', 'T-0016', 'blocked_on', '"fixture de pruebas"'); mutate(tp, 'task', 'T-0016', 'review_ref', None)
        mutate(tp, 'task', 'T-0016', 'requires_decisions', '["D-0007", "D-0014"]'); mutate(tp, 'task', 'T-0016', 'evidence', None)
        mutate(tp, 'task', 'T-0029', 'status', '"ready"')            # T-0029 depende de T-0016: no puede estar hecha si el fixture de T-0016 está bloqueado
        self.render()                                              # las vistas generadas siguen al dato (las pruebas de independencia comprueban 'render --check')

    def tearDown(self): shutil.rmtree(self.d, ignore_errors=True)       # only this test's own temporary copy

    def path(self, *p): return os.path.join(self.d, 'governance', *p)
    def data(self, f): return self.path('data', f)

    def edit(self, rel, fn):
        p = self.path(*rel.split('/')); s = open(p, encoding='utf-8').read(); t = fn(s)
        self.assertNotEqual(s, t, 'the mutation changed nothing: %s' % rel); open(p, 'w', encoding='utf-8').write(t)

    def render(self):
        with contextlib.redirect_stdout(io.StringIO()): gov.cmd_render(self.d, False)

    def repin(self):
        h = hashlib.sha256(open(self.data('policy.toml'), 'rb').read()).hexdigest()
        self.edit('data/policy.pin.toml', lambda s: re.sub(r'sha256 = "[0-9a-f]+"', 'sha256 = "%s"' % h, s))

    def errors(self, render=True, strict=False):
        if render: self.render()
        return gov.check(self.d, use_git=False, strict=strict)[0]

    def assertErr(self, needle, render=True):
        errs = self.errors(render); self.assertTrue(any(needle in e for e in errs), (needle, errs))

    def assertNoErr(self, needle, render=True):
        errs = self.errors(render); self.assertFalse(any(needle in e for e in errs), (needle, errs))

    def authorize(self, ref='D-0050', actions='["delete-or-overwrite"]', extra=''):
        with open(self.data('decisions.toml'), 'a') as f:
            f.write('\n[[decision]]\nid = "%s"\ntitle = "t"\ndate = "2026-11-13"\nscope = "operation"\nstatus = "APPROVED"\nproposer = "ingeniero"\napproved_by = "director"\n'
                    'approval_date = "2026-11-13"\napproval_ref = "mensaje"\nrationale = "r"\nreversal = "x"\nauthorizes = %s\n%s' % (ref, actions, extra))


class Positive(unittest.TestCase):
    def test_real_governance_is_valid(self):
        errs, warns = gov.check(REPO, use_git=True); self.assertEqual(errs, [], errs)

    def test_real_governance_is_valid_in_strict_mode_except_for_the_state_anchor(self):
        errs, _ = gov.check(REPO, use_git=True, strict=True); self.assertTrue(all('STATE.md describe el commit' in e for e in errs), errs)

    def test_views_are_current(self): self.assertEqual(gov.cmd_render(REPO, True), 0)

    def test_exit_codes_of_can_by_tier(self):
        for action, code in (('read-analysis', 0), ('patch-series-change', 10), ('publish', 20), ('privileged-or-mount', 0), ('heavy-compile', 0), ('device-write-boot', 20),
                             ('write-protected-partitions', 30), ('destructive-git', 30), ('no-existe', 2)):
            self.assertEqual(run(REPO, 'can', action).returncode, code, action)

    def test_cli_read_only_commands_succeed(self):
        for a in (['status'], ['next'], ['render', '--check'], ['check'], ['evidence'], ['regress', '--list']): self.assertEqual(run(REPO, *a).returncode, 0, a)


class Structure(Base):
    def test_missing_required_document(self):
        os.remove(self.path('HANDOFF.md')); self.assertErr('falta governance/HANDOFF.md', render=False)

    def test_missing_data_file(self):
        os.remove(self.data('evidence.toml')); self.assertErr('falta governance/data/evidence.toml', render=False)

    def test_invalid_toml(self):
        self.edit('data/tasks.toml', lambda s: s + '\n[[task\n'); self.assertErr('TOML inválido', render=False)

    def test_stale_generated_view(self):
        self.render(); self.edit('TASKS.md', lambda s: s.replace('# Cola de tareas', '# Cola de tareas EDITADA A MANO')); self.assertErr('TASKS.md está desactualizado', render=False)

    def test_broken_link_in_a_document_and_in_a_checkpoint(self):
        self.edit('README.md', lambda s: s + '\nVer [nada](NO_EXISTE.md)\n'); self.assertErr('enlace roto -> NO_EXISTE.md')
        open(self.path('checkpoints', 'x.md'), 'w').write('[roto](../NADA.md)\n'); self.assertErr('checkpoints/x.md: enlace roto')

    def test_agents_md_must_point_to_governance(self):
        p = os.path.join(self.d, 'AGENTS.md'); s = open(p).read(); open(p, 'w').write(s.replace('governance/README.md', 'otra-cosa')); self.assertErr('AGENTS.md no apunta')

    def test_state_without_commit_marker(self):
        self.edit('STATE.md', lambda s: re.sub(r'<!-- state-commit: [0-9a-f]+ -->', '', s)); self.assertErr('STATE.md sin la marca')


class Tasks(Base):
    def t(self, ident, key, value=None): mutate(self.data('tasks.toml'), 'task', ident, key, value)

    def test_two_tasks_in_progress(self):
        self.t('T-0008', 'status', '"in_progress"'); self.t('T-0010', 'status', '"in_progress"'); self.assertErr('más de una tarea en curso')

    def test_dependency_on_missing_task(self):
        self.t('T-0004', 'depends_on', '["T-9999"]'); self.assertErr('depende de una tarea inexistente T-9999')

    def test_dependency_cycle(self):
        self.t('T-0008', 'depends_on', '["T-0010"]'); self.t('T-0010', 'depends_on', '["T-0008"]'); self.assertErr('ciclo de dependencias')

    def test_unknown_action_is_an_error_and_fails_closed(self):
        self.t('T-0008', 'actions', '["inventada"]'); self.assertErr("acción desconocida 'inventada'")
        self.assertEqual(gov.tier_of_actions(gov.load(self.d, 'policy.toml'), ['inventada']), 'X')              # fail-closed, not green

    def test_blocked_without_reason_and_ready_with_reason(self):
        self.t('T-0004', 'blocked_on', None); self.assertErr('bloqueada sin blocked_on')
        self.t('T-0022', 'status', '"ready"'); self.t('T-0022', 'blocked_on', '"algo"'); self.assertErr('está ready pero declara blocked_on')   # no depende del estado real

    def test_c_action_in_progress_without_authorization(self):
        self.t('T-0007', 'status', '"in_progress"'); self.assertErr('acción C en curso/hecha sin authorization_ref')

    def test_authorization_by_an_unrelated_director_decision_is_rejected(self):
        self.t('T-0007', 'status', '"in_progress"'); self.t('T-0007', 'authorization_ref', '"D-0005"')      # D-0005 is APPROVED by the director but authorizes nothing
        self.assertErr('no autoriza la acción delete-or-overwrite')

    def test_authorization_that_names_the_action_is_accepted(self):
        self.authorize(); self.t('T-0007', 'status', '"in_progress"'); self.t('T-0007', 'authorization_ref', '"D-0050"'); self.assertNoErr('T-0007')

    def test_expired_authorization_is_rejected(self):
        self.authorize(extra='valid_until = "2020-01-01"\n'); self.t('T-0007', 'status', '"in_progress"'); self.t('T-0007', 'authorization_ref', '"D-0050"'); self.assertErr('caducó el 2020-01-01')

    def test_authorizes_needs_director_approval_and_only_red_actions(self):
        with open(self.data('decisions.toml'), 'a') as f:
            f.write('\n[[decision]]\nid = "D-0051"\ntitle = "t"\ndate = "2026-11-13"\nscope = "operation"\nstatus = "PROPOSED"\nproposer = "ingeniero"\nrationale = "r"\nreversal = "x"\nauthorizes = ["publish"]\n')
        self.assertErr('D-0051: authorizes exige estado APPROVED, aprobador director y ámbito operation')
        self.authorize('D-0052', '["read-analysis"]'); self.assertErr('authorizes solo puede citar acciones de nivel C')

    def test_forbidden_action_in_a_live_task(self):
        self.t('T-0014', 'actions', '["destructive-git"]'); self.assertErr('contiene una acción prohibida (X)')

    def test_done_with_unfinished_dependency_and_in_progress_with_unfinished_dependency(self):
        self.t('T-0002', 'depends_on', '["T-0004"]'); self.assertErr('done con dependencia T-0004 sin terminar')
        self.t('T-0008', 'status', '"in_progress"'); self.t('T-0008', 'depends_on', '["T-0006"]'); self.assertErr('en curso pero su dependencia T-0006 no está done')

    def test_yellow_task_cannot_become_done_without_a_recorded_review(self):
        self.t('T-0016', 'status', '"done"'); self.t('T-0016', 'depends_on', '[]'); self.t('T-0016', 'requires_decisions', '[]'); self.t('T-0016', 'blocked_on', None)
        self.assertErr('exige review_ref a una decisión APPROVED de jefe-tecnico o director antes de pasar a done')
        self.t('T-0016', 'review_ref', '"D-0003"'); self.assertNoErr('antes de pasar a done')                       # D-0003 is APPROVED by jefe-tecnico

    def test_a_proposal_cannot_be_the_review(self):
        self.t('T-0016', 'status', '"done"'); self.t('T-0016', 'depends_on', '[]'); self.t('T-0016', 'requires_decisions', '[]'); self.t('T-0016', 'blocked_on', None)
        self.t('T-0016', 'review_ref', '"D-0007"'); self.assertErr('exige review_ref')                          # D-0007 is only PROPOSED

    def test_task_advanced_while_a_required_decision_is_not_approved(self):
        self.t('T-0016', 'status', '"in_progress"'); self.t('T-0016', 'depends_on', '[]'); self.t('T-0016', 'blocked_on', None); self.assertErr('avanzada sin que la decisión D-0007 esté APPROVED')

    def test_min_evidence_is_never_raised_automatically(self):
        self.t('T-0012', 'status', '"in_review"'); self.t('T-0012', 'depends_on', '[]'); self.t('T-0012', 'authorization_ref', '"D-0050"'); self.authorize('D-0050', '["device-read","device-write-boot"]')
        self.assertErr('exige evidencia L3 en this-unit')                                                      # its evidence is host L2 / device data

    def test_schema_types_and_duplicates(self):
        self.t('T-0008', 'depends_on', '"T-0009"'); self.assertErr('depends_on debe ser una lista de cadenas')
        self.t('T-0008', 'priority', '"alta"'); self.assertErr('priority debe ser un entero')
        self.edit('data/tasks.toml', lambda s: s.replace('id = "T-0019"', 'id = "T-0018"', 1)); self.assertErr('tarea duplicada T-0018')
        self.t('T-0001', 'status', '"casi-hecha"'); self.assertErr("estado inválido 'casi-hecha'")
        self.t('T-0008', 'owner', '"becario"'); self.assertErr("propietario desconocido 'becario'")

    def test_task_referencing_missing_evidence(self):
        self.t('T-0007', 'evidence', '["E-9999"]'); self.assertErr('evidencia inexistente E-9999')


class Selection(unittest.TestCase):
    """Selection rules on SYNTHETIC data (the real queue changes every day; the rules must not depend on it)."""
    POLICY = {'actions': [{'id': 'a', 'tier': 'A'}, {'id': 'b', 'tier': 'B'}, {'id': 'c', 'tier': 'C'}, {'id': 'x', 'tier': 'X'}]}

    def task(self, i, **kw):
        t = {'id': 'T-%04d' % i, 'status': 'ready', 'priority': 5, 'owner': 'ingeniero', 'depends_on': [], 'actions': ['a']}; t.update(kw); return t

    def pick(self, *tasks, decisions=()):
        return gov.next_task(self.POLICY, {'task': list(tasks)}, {'decision': list(decisions)})

    def test_the_real_queue_selects_a_task_that_satisfies_every_rule(self):
        policy, tasks, decs = (gov.load(REPO, f) for f in ('policy.toml', 'tasks.toml', 'decisions.toml')); n, mode = gov.next_task(policy, tasks, decs)
        if n is None: return
        by = {t['id']: t for t in tasks['task']}
        self.assertIn(mode, ('start', 'resume')); self.assertEqual(n['owner'], 'ingeniero')
        if mode == 'resume' and gov.tier_of_actions(policy, n['actions']) == 'C': self.assertTrue(n.get('authorization_ref'), 'reanudar una tarea roja exige su authorization_ref')   # una tarea ya en curso con su autorización registrada
        else: self.assertIn(gov.tier_of_actions(policy, n['actions']), ('A', 'B'))
        if mode == 'start':
            self.assertEqual(n['status'], 'ready'); self.assertFalse(n.get('blocked_on')); self.assertTrue(all(by[d]['status'] == 'done' for d in n.get('depends_on', [])))

    def test_blocked_tasks_are_never_selected(self):
        self.assertEqual(self.pick(self.task(1, status='blocked'), self.task(2, status='blocked')), (None, None))

    def test_dependencies_are_respected(self):
        n, _ = self.pick(self.task(1, depends_on=['T-0003'], priority=1), self.task(2, priority=9), self.task(3, status='blocked')); self.assertEqual(n['id'], 'T-0002')
        n, _ = self.pick(self.task(1, depends_on=['T-0003'], priority=1), self.task(3, status='done')); self.assertEqual(n['id'], 'T-0001')
        self.assertEqual(self.pick(self.task(1, depends_on=['T-9999'])), (None, None))                     # a dependency that does not exist is never satisfied

    def test_priority_then_id_order(self):
        n, _ = self.pick(self.task(3, priority=2), self.task(2, priority=2), self.task(1, priority=7)); self.assertEqual(n['id'], 'T-0002')

    def test_tasks_owned_by_someone_else_are_not_selected(self):
        self.assertEqual(self.pick(self.task(1, owner='director'), self.task(2, owner='jefe-tecnico')), (None, None))

    def test_red_forbidden_and_unknown_actions_are_never_selected(self):
        self.assertEqual(self.pick(self.task(1, actions=['c']), self.task(2, actions=['x']), self.task(3, actions=['inventada']), self.task(4, actions=['a', 'c']), self.task(5, actions=[])), (None, None))

    def test_a_ready_task_that_declares_blocked_on_is_not_selected(self):
        n, _ = self.pick(self.task(1, blocked_on='algo', priority=1), self.task(2)); self.assertEqual(n['id'], 'T-0002')

    def test_required_decisions_must_be_approved(self):
        t = self.task(1, requires_decisions=['D-0001'])
        self.assertEqual(self.pick(t, decisions=[{'id': 'D-0001', 'status': 'PROPOSED'}]), (None, None))
        self.assertEqual(self.pick(t, decisions=[]), (None, None))
        n, _ = self.pick(t, decisions=[{'id': 'D-0001', 'status': 'APPROVED'}]); self.assertEqual(n['id'], 'T-0001')

    def test_the_task_in_progress_is_resumed_before_anything_new(self):
        n, mode = self.pick(self.task(1, priority=1), self.task(2, status='in_progress', priority=9)); self.assertEqual((n['id'], mode), ('T-0002', 'resume'))

    def test_a_yellow_task_is_selected_only_as_local_work(self):
        n, _ = self.pick(self.task(1, actions=['b'])); self.assertEqual(n['id'], 'T-0001'); self.assertEqual(gov.tier_of_actions(self.POLICY, n['actions']), 'B')
        d = tempfile.mkdtemp(prefix='gov-sel.')
        try:
            shutil.copytree(os.path.join(REPO, 'governance'), os.path.join(d, 'governance'), ignore=shutil.ignore_patterns('__pycache__'))
            self.assertEqual(run(d, 'gate', 'patch-series-change').returncode, 10)                          # allowed locally, never "integrated"
        finally: shutil.rmtree(d, ignore_errors=True)

    def test_a_task_with_a_non_integer_priority_is_ignored_not_a_crash(self):
        n, _ = self.pick(self.task(1, priority='alta'), self.task(2)); self.assertEqual(n['id'], 'T-0002')


class Gate(Base):
    def g(self, *a): return run(self.d, 'gate', *a)

    def test_green_yellow_red_forbidden_unknown(self):
        self.assertEqual(self.g('docs-write').returncode, 0)
        self.assertEqual(self.g('patch-series-change').returncode, 10)
        self.assertEqual(self.g('publish').returncode, 20)
        self.assertEqual(self.g('write-protected-partitions').returncode, 30)
        self.assertEqual(self.g('inventada').returncode, 2)

    def test_red_is_denied_without_a_task_or_without_a_reference(self):
        self.assertEqual(self.g('delete-or-overwrite').returncode, 20)
        self.assertEqual(self.g('delete-or-overwrite', '--task', 'T-0007').returncode, 20)
        self.assertEqual(self.g('delete-or-overwrite', '--task', 'T-9999').returncode, 20)

    def test_red_is_denied_with_an_unrelated_approved_decision(self):
        mutate(self.data('tasks.toml'), 'task', 'T-0007', 'authorization_ref', '"D-0005"'); r = self.g('delete-or-overwrite', '--task', 'T-0007')
        self.assertEqual(r.returncode, 20); self.assertIn('no autoriza la acción', r.stdout)

    def test_red_is_registered_only_with_a_matching_director_decision_and_never_executes(self):
        self.authorize(); mutate(self.data('tasks.toml'), 'task', 'T-0007', 'authorization_ref', '"D-0050"'); r = self.g('delete-or-overwrite', '--task', 'T-0007')
        self.assertEqual(r.returncode, 0); self.assertIn('NO ejecuta nada', r.stdout)

    def test_red_is_denied_if_the_task_does_not_declare_the_action(self):
        self.authorize('D-0050', '["publish"]'); mutate(self.data('tasks.toml'), 'task', 'T-0007', 'authorization_ref', '"D-0050"')
        self.assertEqual(self.g('publish', '--task', 'T-0007').returncode, 20)

    def test_red_is_denied_if_expired_or_if_not_by_the_director(self):
        self.authorize(extra='valid_until = "2020-01-01"\n'); mutate(self.data('tasks.toml'), 'task', 'T-0007', 'authorization_ref', '"D-0050"')
        self.assertEqual(self.g('delete-or-overwrite', '--task', 'T-0007').returncode, 20)
        mutate(self.data('decisions.toml'), 'decision', 'D-0050', 'approved_by', '"jefe-tecnico"'); mutate(self.data('decisions.toml'), 'decision', 'D-0050', 'valid_until', None)
        self.assertEqual(self.g('delete-or-overwrite', '--task', 'T-0007').returncode, 20)

    def test_a_proposed_decision_does_not_authorize(self):
        self.authorize(); mutate(self.data('decisions.toml'), 'decision', 'D-0050', 'status', '"PROPOSED"'); mutate(self.data('tasks.toml'), 'task', 'T-0007', 'authorization_ref', '"D-0050"')
        self.assertEqual(self.g('delete-or-overwrite', '--task', 'T-0007').returncode, 20)

    def test_yellow_consolidation_needs_a_recorded_review(self):
        mutate(self.data('tasks.toml'), 'task', 'T-0016', 'actions', '["patch-series-change"]')
        self.assertEqual(self.g('patch-series-change', '--task', 'T-0016', '--consolidate').returncode, 12)
        mutate(self.data('tasks.toml'), 'task', 'T-0016', 'review_ref', '"D-0007"'); self.assertEqual(self.g('patch-series-change', '--task', 'T-0016', '--consolidate').returncode, 12)  # PROPOSED
        mutate(self.data('tasks.toml'), 'task', 'T-0016', 'review_ref', '"D-0003"'); self.assertEqual(self.g('patch-series-change', '--task', 'T-0016', '--consolidate').returncode, 11)

    def test_policy_change_is_reviewed_by_the_director_only(self):
        mutate(self.data('tasks.toml'), 'task', 'T-0001', 'actions', '["policy-change"]'); mutate(self.data('tasks.toml'), 'task', 'T-0001', 'review_ref', '"D-0003"')
        self.assertEqual(self.g('policy-change', '--task', 'T-0001', '--consolidate').returncode, 12)          # D-0003 is the technical lead's, the reviewer must be the director
        mutate(self.data('tasks.toml'), 'task', 'T-0001', 'review_ref', '"D-0005"'); self.assertEqual(self.g('policy-change', '--task', 'T-0001', '--consolidate').returncode, 11)

    def test_can_and_check_say_they_are_not_authorizations(self):
        self.assertIn('no es una autorización', run(self.d, 'can', 'publish').stdout)
        self.assertIn('no autoriza ninguna acción', run(self.d, 'status').stdout)
        self.assertIn('no es una autorización', run(self.d, 'next').stdout)


class Evidence(Base):
    def setUp(self):
        super().setUp(); self.f = os.path.join(self.d, 'artefacto.bin'); open(self.f, 'wb').write(b'contenido')
        self.h = hashlib.sha256(b'contenido').hexdigest()
        self.rec = lambda i, path, **kw: ('[[evidence]]\nid = "%s"\ntitle = "t%s"\nkind = "artifact"\npath = "%s"\nlocation = "host"\ncreated = "2026-11-13"\ndomain = "host"\nlevel = "L2"\ndevice = "none"\n' % (i, i, path)
                                          + ''.join('%s = %s\n' % kv for kv in kw.items()))

    def put(self, *recs): open(self.data('evidence.toml'), 'w').write('\n'.join(recs))
    def ev(self, *a): return run(self.d, 'evidence', *a)

    def test_ok_only_when_the_hash_and_size_match(self):
        self.put(self.rec('E-0001', self.f, sha256='"%s"' % self.h, size=9, immutable='true')); r = self.ev(); self.assertEqual(r.returncode, 0); self.assertIn('OK', r.stdout)

    def test_modified_immutable_evidence_fails(self):
        self.put(self.rec('E-0001', self.f, sha256='"%s"' % self.h, immutable='true')); open(self.f, 'wb').write(b'alterado!'); r = self.ev()
        self.assertEqual(r.returncode, 1); self.assertIn('MODIFICADA', r.stdout)

    def test_outdated_mutable_evidence_is_reported_as_outdated_and_fails(self):
        self.put(self.rec('E-0001', self.f, sha256='"%s"' % self.h, immutable='false')); open(self.f, 'wb').write(b'alterado!'); r = self.ev()
        self.assertEqual(r.returncode, 1); self.assertIn('DESACTUALIZADA', r.stdout)

    def test_size_mismatch_is_caught_before_hashing(self):
        self.put(self.rec('E-0001', self.f, sha256='"%s"' % self.h, size=999)); r = self.ev(); self.assertEqual(r.returncode, 1); self.assertIn('TAMAÑO', r.stdout)

    def test_a_symlink_is_not_evidence(self):
        ln = os.path.join(self.d, 'enlace.bin'); os.symlink(self.f, ln); self.put(self.rec('E-0001', ln, sha256='"%s"' % self.h)); r = self.ev()
        self.assertEqual(r.returncode, 1); self.assertIn('SYMLINK', r.stdout)

    def test_a_record_without_hash_is_never_ok(self):
        self.put(self.rec('E-0001', self.f)); r = self.ev(); self.assertIn('SIN-HASH', r.stdout); self.assertNotIn('\nOK ', '\n' + r.stdout)
        self.assertEqual(self.ev('--strict').returncode, 1)

    def test_absent_evidence_is_not_valid_and_strict_mode_fails(self):
        self.put(self.rec('E-0001', '/no/existe/aqui.bin', sha256='"%s"' % self.h, immutable='true')); r = self.ev()
        self.assertEqual(r.returncode, 0); self.assertIn('AUSENTE', r.stdout); self.assertNotIn('OK', r.stdout.split('RESUMEN')[0]); self.assertEqual(self.ev('--strict').returncode, 1)

    def test_summary_states_that_levels_are_never_raised(self):
        self.put(self.rec('E-0001', self.f, sha256='"%s"' % self.h)); self.assertIn('Ningún resultado eleva el nivel', self.ev().stdout)

    def test_levels_domains_and_devices_are_declared_and_cannot_be_promoted(self):
        errs = lambda: self.errors()
        mutate(self.data('evidence.toml'), 'evidence', 'E-0001', 'level', '"L3"'); self.assertTrue(any('una prueba host no puede declarar L3' in e for e in errs()))
        mutate(self.data('evidence.toml'), 'evidence', 'E-0001', 'level', '"L2"'); mutate(self.data('evidence.toml'), 'evidence', 'E-0007', 'level', '"L2"')
        self.assertTrue(any('un resultado de compilación es L1' in e for e in errs()))
        mutate(self.data('evidence.toml'), 'evidence', 'E-0007', 'level', '"L1"'); mutate(self.data('evidence.toml'), 'evidence', 'E-0001', 'domain', '"gpu-device"')
        self.assertTrue(any('GPU física' in e or 'el dominio gpu-device exige' in e for e in errs()))
        mutate(self.data('evidence.toml'), 'evidence', 'E-0001', 'domain', '"host"'); mutate(self.data('evidence.toml'), 'evidence', 'E-0009', 'level', '"L3"'); mutate(self.data('evidence.toml'), 'evidence', 'E-0009', 'device', '"none"')
        self.assertTrue(any('exige device this-unit o upstream-device' in e for e in errs()))

    def test_ios_integration_is_l4_and_gpu_is_l3(self):
        self.put(self.rec('E-0001', self.f, sha256='"%s"' % self.h).replace('domain = "host"\nlevel = "L2"\ndevice = "none"', 'domain = "ios-integration"\nlevel = "L3"\ndevice = "this-unit"'))
        self.assertTrue(any('integración iOS es L4' in e for e in self.errors(render=False)))

    def test_immutable_without_hash_and_malformed_hash(self):
        mutate(self.data('evidence.toml'), 'evidence', 'E-0001', 'sha256', '""'); self.assertErr('evidencia inmutable sin SHA-256 válido')
        mutate(self.data('evidence.toml'), 'evidence', 'E-0002', 'sha256', '"zzz"'); self.assertErr('SHA-256 mal formado')

    def test_real_index_never_claims_hardware_evidence_for_this_unit(self):
        e = gov.load(REPO, 'evidence.toml')['evidence']
        self.assertEqual([x['id'] for x in e if x['level'] in ('L3', 'L4') and x['device'] == 'this-unit'], [])


class Regress(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.mkdtemp(prefix='gov-regress.'); self.c = make_clone(self.tmp)
    def tearDown(self): shutil.rmtree(self.tmp, ignore_errors=True)

    def suites(self, body, scripts=None):
        for name, code in (scripts or {}).items(): open(os.path.join(self.c, 'tools', name), 'w').write(code)
        open(os.path.join(self.c, 'governance', 'data', 'regression.toml'), 'w').write(body)

    S = '[[suite]]\nid = "%s"\ntitle = "t"\ncommand = %s\nbaseline = "b"\ndomain = "host"\nlevel = "L2"\n%s\n'
    def go(self, *a): return run(self.c, 'regress', *a, git=True)

    def test_statuses_pass_fail_skip_xfail_xpass(self):
        self.suites(self.S % ('pasa', '["true"]', '') + self.S % ('falla', '["false"]', '') + self.S % ('salta', '["true"]', 'requires = ["/no/existe"]') +
                    self.S % ('deuda', '["false"]', 'known_failing = true\nknown_failure_count = 1\nknown_failure_pattern = "x"'))
        r = self.go(); self.assertEqual(r.returncode, 1, r.stdout)
        for want in ('PASS  pasa', 'FALLA falla', 'SKIP  salta', 'XFAIL deuda'): self.assertIn(want, r.stdout)

    def test_known_debt_is_quantified_and_growth_fails(self):
        sc = {'_gap.py': 'import sys\nfor i in range(%d): print("Gap in patch sequence", i)\nsys.exit(1)\n'}
        body = lambda n: self.S % ('deuda', '["python3", "tools/_gap.py"]', 'known_failing = true\nknown_failure_count = %d\nknown_failure_pattern = "Gap in patch sequence"' % n)
        self.suites(body(5), {'_gap.py': sc['_gap.py'] % 5}); r = self.go(); self.assertEqual(r.returncode, 0, r.stdout); self.assertIn('XFAIL', r.stdout); self.assertIn('línea base 5', r.stdout)
        self.suites(body(5), {'_gap.py': sc['_gap.py'] % 7}); r = self.go(); self.assertEqual(r.returncode, 1); self.assertIn('HAN AUMENTADO', r.stdout)

    def test_unsafe_commands_are_refused_by_the_screen_and_by_check(self):
        bad = ['["sudo", "true"]', '["bash", "-c", "echo hi"]', '["python3", "/etc/passwd"]', '["python3", "../fuera.py"]', '["git", "push"]', '["rm", "-rf", "x"]', '["mount"]', '["adb", "devices"]',
               '["python3", "-c", "print(1)"]', '["./../x"]', '[]']
        for cmd in bad:
            self.suites(self.S % ('mala', cmd, '')); r = self.go()
            self.assertEqual(r.returncode, 1, cmd); self.assertIn('RECHAZADA', r.stdout, cmd)
            self.assertTrue(any('suite mala' in e for e in gov.check(self.c, use_git=False)[0]), cmd)

    def test_read_only_git_and_repo_scripts_are_accepted(self):
        for cmd in ('["git", "status"]', '["python3", "-I", "tools/governance.py", "can", "publish"]', '["bash", "-n", "tools/test_tune_ios_root.sh"]'):
            self.assertEqual(gov.screen_command(self.c, __import__('ast').literal_eval(cmd)), [], cmd)

    def test_a_suite_that_modifies_the_git_tree_fails(self):
        self.suites(self.S % ('ensucia', '["python3", "tools/_w.py"]', ''), {'_w.py': 'open("basura.txt", "w").write("x")\n'}); r = self.go()
        self.assertEqual(r.returncode, 1); self.assertIn('MODIFICÓ EL ÁRBOL GIT', r.stdout)

    def test_timeout_is_a_failure_not_a_crash(self):
        self.suites(self.S % ('lenta', '["python3", "tools/_s.py"]', 'timeout = 1'), {'_s.py': 'import time\ntime.sleep(5)\n'}); r = self.go()
        self.assertEqual(r.returncode, 1); self.assertIn('tiempo agotado', r.stdout); self.assertNotIn('Traceback', r.stderr)

    def test_unknown_suite_and_strict_skips(self):
        self.suites(self.S % ('salta', '["true"]', 'requires = ["/no/existe"]'))
        self.assertEqual(self.go('--suite', 'inexistente').returncode, 2); self.assertEqual(self.go().returncode, 0); self.assertEqual(self.go('--strict').returncode, 1)

    def test_every_suite_declares_domain_and_level_and_none_claims_hardware(self):
        for s in gov.load(REPO, 'regression.toml')['suite']:
            self.assertIn(s['domain'], ('host', 'build')); self.assertIn(s['level'], ('L1', 'L2'))

    def test_validate_repo_debt_is_quantified_in_the_real_data(self):
        s = [x for x in gov.load(REPO, 'regression.toml')['suite'] if x['id'] == 'validate-repo'][0]
        self.assertTrue(s['known_failing']); self.assertEqual(s['known_failure_count'], 5); self.assertEqual(s['known_failure_pattern'], 'Gap in patch sequence')


class Render(Base):
    def test_render_writes_only_the_four_generated_views(self):
        self.edit('data/tasks.toml', lambda s: s.replace('priority = 3', 'priority = 33', 1)); before = snapshot(self.d); self.render(); after = snapshot(self.d)
        changed = {k for k in set(before) | set(after) if before.get(k) != after.get(k)}
        self.assertTrue(changed and changed <= {os.path.join('governance', v) for v in gov.GENERATED_VIEWS}, changed)
        self.assertFalse([k for k in after if k.endswith('.tmp')])

    def test_render_refuses_any_other_file_name(self):
        for fn in ('README.md', '../AGENTS.md', 'data/policy.toml', 'STATE.md'):
            with self.assertRaises(gov.DataError): gov.write_generated(self.d, fn, 'x')

    def test_render_refuses_to_overwrite_a_hand_written_file(self):
        open(self.path('TASKS.md'), 'w').write('# Mi lista a mano\n'); r = run(self.d, 'render')
        self.assertEqual(r.returncode, 3); self.assertEqual(open(self.path('TASKS.md')).read(), '# Mi lista a mano\n')

    def test_render_refuses_a_symlink(self):
        os.remove(self.path('TASKS.md')); os.symlink('/etc/hostname', self.path('TASKS.md')); r = run(self.d, 'render'); self.assertEqual(r.returncode, 3)

    def test_render_is_atomic_when_the_write_fails(self):
        self.edit('data/tasks.toml', lambda s: s.replace('priority = 3', 'priority = 33', 1)); orig = open(self.path('TASKS.md')).read(); real = os.replace
        def boom(a, b): raise OSError('disco lleno simulado')
        os.replace = boom
        try:
            with self.assertRaises(OSError): gov.write_generated(self.d, 'TASKS.md', 'nuevo')
        finally: os.replace = real
        self.assertEqual(open(self.path('TASKS.md')).read(), orig); self.assertEqual([f for f in os.listdir(self.path()) if f.startswith('.render-')], [])

    def test_a_data_error_leaves_every_view_untouched(self):
        before = snapshot(self.path()); self.edit('data/decisions.toml', lambda s: s.replace('[[decision]]\nid = "D-0001"', '[[decision]]\n', 1)); r = run(self.d, 'render')
        self.assertIn(r.returncode, (3,)); after = snapshot(self.path()); changed = {k for k in after if before.get(k) != after.get(k)}
        self.assertEqual(changed, {os.path.join('data', 'decisions.toml')})

    def test_render_check_does_not_write(self):
        self.edit('TASKS.md', lambda s: s + 'x'); before = snapshot(self.d); r = run(self.d, 'render', '--check'); self.assertEqual(r.returncode, 1); self.assertEqual(snapshot(self.d), before)


class ReadOnly(unittest.TestCase):
    """The whole clone, .git included, must be byte-identical after every read-only command."""
    @classmethod
    def setUpClass(cls): cls.tmp = tempfile.mkdtemp(prefix='gov-ro.'); cls.c = make_clone(cls.tmp)
    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_read_only_commands_leave_the_tree_and_git_untouched(self):
        for args in (['check'], ['check', '--strict'], ['render', '--check'], ['can', 'publish'], ['gate', 'publish'], ['gate', 'docs-write'], ['next'], ['status'], ['evidence'], ['evidence', '--strict'],
                     ['regress', '--list']):
            before = snapshot(self.c); run(self.c, *args, git=True); self.assertEqual(snapshot(self.c), before, args)

    def test_a_dirty_tree_is_not_cleaned_or_refreshed(self):
        open(os.path.join(self.c, 'sin_confirmar.txt'), 'w').write('x'); os.utime(os.path.join(self.c, 'AGENTS.md'), (1, 1)); before = snapshot(self.c)
        for args in (['status'], ['check'], ['regress', '--list']): run(self.c, *args, git=True)
        self.assertEqual(snapshot(self.c), before); os.remove(os.path.join(self.c, 'sin_confirmar.txt'))

    def test_git_is_always_invoked_without_optional_locks(self):
        src = open(TOOL).read(); self.assertIn("'--no-optional-locks'", src); self.assertIn("GIT_OPTIONAL_LOCKS='0'", src)
        used = set(re.findall(r"\bgit\((?:root|a\.root), '([a-z-]+)'", src)); self.assertTrue(used)
        self.assertLessEqual(used, {'rev-parse', 'status', 'log', 'branch', 'worktree', 'cat-file', 'merge-base', 'rev-list'})      # every git call the tool makes is a read

    def test_the_tool_never_uses_a_shell_or_deletes_anything(self):
        src = open(TOOL).read()
        for bad in ('shell=True', 'os.system', 'os.remove(', 'shutil.rmtree', 'os.rmdir'): self.assertNotIn(bad, src)
        self.assertEqual(src.count('os.unlink('), 1)                       # only the cleanup of its own temporary render file


class Robustness(Base):
    BAD = {
        'tasks.toml': ['task = "x"\n', '[[task]]\nid = 5\n', '[[task]]\nid = "T-0001"\nstatus = ["a"]\nactions = "x"\n', '[[task]]\n'],
        'decisions.toml': ['decision = 3\n', '[[decision]]\nid = "D-0001"\nstatus = 7\n', '[[decision]]\n'],
        'evidence.toml': ['evidence = "x"\n', '[[evidence]]\nid = "E-0001"\nsize = "grande"\n', '[[evidence]]\n'],
        'regression.toml': ['suite = 1\n', '[[suite]]\nid = "x"\ncommand = "ls"\n', '[[suite]]\n'],
        'policy.toml': ['actions = "x"\n', '[[actions]]\nid = 7\n', 'roles = 3\ntiers = 4\n'],
        'policy.pin.toml': ['sha256 = 5\n', ''],
    }

    def test_malformed_data_gives_errors_not_tracebacks(self):
        for fn, cases in self.BAD.items():
            for body in cases:
                orig = open(self.data(fn)).read(); open(self.data(fn), 'w').write(body)
                try:
                    for args in (['check'], ['next'], ['status'], ['render'], ['render', '--check'], ['evidence'], ['regress', '--list'], ['can', 'publish'], ['gate', 'publish'], ['regress']):
                        r = run(self.d, *args); self.assertNotIn('Traceback', r.stderr, (fn, body, args, r.stderr[-300:])); self.assertIn(r.returncode, (0, 1, 2, 3, 20, 30), (fn, args, r.returncode))
                    self.assertEqual(run(self.d, 'check').returncode, 1, (fn, body))
                finally: open(self.data(fn), 'w').write(orig)

    def test_empty_directory_and_missing_root(self):
        e = tempfile.mkdtemp(prefix='gov-empty.')
        try:
            r = run(e, 'check'); self.assertEqual(r.returncode, 1); self.assertNotIn('Traceback', r.stderr)
            for args in (['next'], ['status'], ['evidence'], ['render']): self.assertNotIn('Traceback', run(e, *args).stderr, args)
        finally: shutil.rmtree(e)
        r = run('/no/existe/de/verdad', 'check'); self.assertNotIn('Traceback', r.stderr)

    def test_an_interrupted_render_leaves_no_partial_view(self):
        self.edit('data/tasks.toml', lambda s: s.replace('priority = 3', 'priority = 33', 1)); self.edit('data/decisions.toml', lambda s: s.replace('Sistema de gobierno de ingeniería autónoma', 'Sistema de gobierno RENOMBRADO', 1))
        before = {v: open(self.path(v)).read() for v in gov.GENERATED_VIEWS}
        real = gov.write_generated; calls = []
        def flaky(root, fn, text):
            calls.append(fn)
            if len(calls) == 2: raise OSError('corte simulado')
            return real(root, fn, text)
        gov.write_generated = flaky
        try:
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(OSError): gov.cmd_render(self.d, False)
        finally: gov.write_generated = real
        for v in gov.GENERATED_VIEWS: self.assertIn(open(self.path(v)).read(), (before[v], gov.render_all(self.d)[v]))     # each view is either the old or the new text, never a mix
        self.assertEqual(run(self.d, 'render').returncode, 0); self.assertEqual(run(self.d, 'render', '--check').returncode, 0)    # re-running recovers


class PolicyPin(Base):
    def test_downgrading_an_action_is_detected(self):
        self.edit('data/policy.toml', lambda s: s.replace('id = "publish"\ntier = "C"\nauthorizer = "director"', 'id = "publish"\ntier = "A"', 1)); self.assertErr('policy.toml cambió sin actualizar policy.pin.toml')

    def test_updating_the_pin_is_a_visible_second_step(self):
        self.edit('data/policy.toml', lambda s: s.replace('id = "publish"\ntier = "C"\nauthorizer = "director"', 'id = "publish"\ntier = "A"', 1)); self.assertErr('policy.pin.toml')
        self.repin(); self.assertNoErr('policy.pin.toml')

    def test_the_pin_does_not_ratify_the_policy(self):
        # el pin no ratifica nada: si D-0001 deja de estar APPROVED, la herramienta avisa de que la política es una propuesta
        def unratify(s):
            i = s.index('id = "D-0001"'); j = s.index('status = "APPROVED"', i)
            k = s.find('[[decision]]', i); k = len(s) if k < 0 else k
            assert j < k
            return s[:j] + 'status = "PROPOSED"' + s[j + len('status = "APPROVED"'):]
        self.edit('data/decisions.toml', unratify); self.render()
        warns = gov.check(self.d, use_git=False)[1]
        self.assertTrue(any('PROPUESTA' in w and 'D-0001' in w for w in warns), warns)

    def test_an_approved_governance_decision_clears_the_proposal_warning(self):
        warns = gov.check(REPO, use_git=False)[1]; self.assertFalse(any('PROPUESTA' in w for w in warns), warns)

    def test_a_tier_colour_must_match(self):
        self.edit('data/policy.toml', lambda s: s.replace('color = "rojo"\nname = "autorización explícita del Director"', 'color = "verde"\nname = "autorización explícita del Director"', 1)); self.repin()
        self.assertErr('el color del nivel C debe ser rojo')


class Independence(Base):
    def test_no_absolute_paths_or_main_tree_reference_in_the_tool(self):
        src = open(TOOL).read()
        for bad in ('/home/', 'wardevsa-ios-a5xelte', '/media/', '/tmp/claude', 'pioxi'): self.assertNotIn(bad, src, bad)

    def test_it_runs_from_a_copy_elsewhere_with_an_empty_home_and_another_cwd(self):
        home = tempfile.mkdtemp(prefix='gov-home.')
        try:
            for args in (['check'], ['next'], ['status'], ['render', '--check'], ['evidence'], ['can', 'publish'], ['gate', 'docs-write']):
                r = run(self.d, *args, env={'HOME': home}, cwd='/'); self.assertIn(r.returncode, (0, 20), (args, r.stdout[-300:], r.stderr[-300:]))
            self.assertIn('AUSENTE', run(self.d, 'evidence', env={'HOME': home}, cwd='/').stdout)                  # machine-specific data is skipped, not required
        finally: shutil.rmtree(home)

    def test_default_root_is_the_repository_that_contains_the_tool(self):
        c = os.path.join(self.d, 'otro'); os.makedirs(os.path.join(c, 'tools')); shutil.copy(TOOL, os.path.join(c, 'tools', 'governance.py'))
        shutil.copytree(self.path(), os.path.join(c, 'governance')); shutil.copy(os.path.join(self.d, 'AGENTS.md'), c)
        r = subprocess.run([sys.executable, '-I', os.path.join(c, 'tools', 'governance.py'), 'render', '--check'], capture_output=True, text=True, cwd='/'); self.assertEqual(r.returncode, 0, r.stdout)

    def test_the_main_work_tree_is_never_read_or_written(self):
        # the tool is given only --root; with a root that has no governance it must complain about THAT root, never fall back to another tree
        e = tempfile.mkdtemp(prefix='gov-nofallback.')
        try: r = run(e, 'check'); self.assertIn('falta governance/', r.stdout)
        finally: shutil.rmtree(e)


class DocsConsistency(unittest.TestCase):
    def test_every_test_cited_by_the_audit_exists(self):
        audit = open(os.path.join(REPO, 'governance', 'AUDIT_GOVERNANCE_TOOL.md'), encoding='utf-8').read()
        have = set()
        for f in ('test_governance.py', 'test_onboarding.py'):
            p = os.path.join(HERE, f)
            if os.path.exists(p): have |= set(re.findall(r'def (test_\w+)', open(p).read()))
        cited = set(re.findall(r'`(test_\w+)`', audit)); self.assertTrue(cited); self.assertEqual(sorted(cited - have), [])

    def test_documents_only_mention_existing_ids_commands_and_tools(self):
        gdir = os.path.join(REPO, 'governance'); text = ''
        for f in ('README.md', 'STATE.md', 'HANDOFF.md', 'ROADMAP.md', 'ARCHITECTURE.md', 'AUTONOMY_POLICY.md', 'AUTHORITY.md', 'KNOWN_ISSUES.md', 'ONBOARDING_DRILL.md'): text += open(os.path.join(gdir, f), encoding='utf-8').read()
        ids = {k: {x['id'] for x in gov.load(REPO, f)[t]} for k, (f, t) in {'T': ('tasks.toml', 'task'), 'D': ('decisions.toml', 'decision'), 'E': ('evidence.toml', 'evidence')}.items()}
        for k, pat in (('T', r'T-\d{4}'), ('D', r'D-\d{4}'), ('E', r'E-\d{4}')):
            for m in set(re.findall(r'(?<![A-Za-z])%s(?!\d)' % pat, text)): self.assertIn(m, ids[k], 'la documentación cita %s que no existe' % m)
        subs = {'check', 'render', 'can', 'gate', 'next', 'status', 'evidence', 'regress'}
        for m in re.findall(r'governance\.py (?:--[a-z-]+ \S+ )?([a-z]+)', text): self.assertIn(m, subs, m)
        for m in set(re.findall(r'`(tools/[A-Za-z0-9_./-]+\.(?:py|sh))`', text)): self.assertTrue(os.path.exists(os.path.join(REPO, m)), m)

    def test_the_policy_colours_are_documented(self):
        t = open(os.path.join(REPO, 'governance', 'AUTONOMY_POLICY.md'), encoding='utf-8').read()
        for w in ('verde', 'amarillo', 'rojo'): self.assertIn(w, t)


if __name__ == '__main__':
    unittest.main(verbosity=1)
