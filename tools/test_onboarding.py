#!/usr/bin/env python3
"""Reproducible onboarding test, part 1 (deterministic). Another agent must be able to take the project over by reading ONLY the repository: this runs the README's
onboarding commands literally in a fresh clone with an EMPTY home directory (no access to the session, to the main work tree or to private data), checks that what the
documents claim matches the real state, and rehearses an interrupted-work resume. Part 2 (a cold model answering questions) is governance/ONBOARDING_DRILL.md.
    python3 -W ignore tools/test_onboarding.py"""
import json, os, re, shlex, shutil, subprocess, sys, tempfile, unittest

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import test_governance as tg
import governance as gov
import onboarding_drill as drill

DRILL = os.path.join(HERE, 'onboarding_drill.py')


class Onboarding(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix='gov-onboard.'); cls.home = os.path.join(cls.tmp, 'home'); os.makedirs(cls.home)
        cls.c = tg.make_clone(cls.tmp); cls.env = dict(os.environ, HOME=cls.home, GIT_AUTHOR_NAME='t', GIT_AUTHOR_EMAIL='t@t', GIT_COMMITTER_NAME='t', GIT_COMMITTER_EMAIL='t@t')

    @classmethod
    def tearDownClass(cls): shutil.rmtree(cls.tmp, ignore_errors=True)         # only this test's own temporary clone

    def sh(self, argv, cwd=None, **kw): return subprocess.run(argv, cwd=cwd or self.c, capture_output=True, text=True, env=self.env, **kw)
    def gov(self, *a, cwd=None): return self.sh([sys.executable, '-I', 'tools/governance.py'] + list(a), cwd=cwd)

    def onboarding_commands(self):
        readme = open(os.path.join(self.c, 'governance', 'README.md'), encoding='utf-8').read()
        sec = readme.split('Si acabas de incorporarte')[1].split('**Tu rol')[0]
        cmds = []
        for line in sec.splitlines():
            line = line.strip()
            if line.startswith('python3 tools/governance.py'): cmds.append(shlex.split(line.split('#')[0]))
        return cmds

    def test_the_readme_onboarding_commands_run_literally_and_change_nothing(self):
        cmds = self.onboarding_commands(); self.assertGreaterEqual(len(cmds), 4)
        self.assertEqual({c[2] for c in cmds}, {'check', 'status', 'next', 'evidence'})
        before = tg.snapshot(self.c)
        for argv in cmds:
            r = self.sh([sys.executable, '-I'] + argv[1:]); self.assertEqual(r.returncode, 0, (argv, r.stdout[-400:], r.stderr[-400:]))
        self.assertEqual(tg.snapshot(self.c), before)

    def test_what_the_documents_claim_matches_the_real_state(self):
        gdir = os.path.join(self.c, 'governance'); rd = lambda f: open(os.path.join(gdir, f), encoding='utf-8').read()
        branch = self.sh(['git', 'branch', '--show-current']).stdout.strip(); self.assertTrue(branch)
        self.assertEqual(re.search(r'rama\s+\*\*`([^`]+)`\*\*', rd('HANDOFF.md')).group(1), branch)
        evid = {e['id']: e for e in gov.load(self.c, 'evidence.toml')['evidence']}
        self.assertIn(evid['E-0001']['sha256'][:8], rd('STATE.md'))
        policy, tasks, decs = (gov.load(self.c, f) for f in ('policy.toml', 'tasks.toml', 'decisions.toml')); n, mode = gov.next_task(policy, tasks, decs)
        self.assertIn(n['id'], rd('ACTIVE_TASK.md')); self.assertIn(n['id'], rd('HANDOFF.md'))
        sha = re.search(r'state-commit: ([0-9a-f]+)', rd('STATE.md')).group(1); self.assertEqual(self.sh(['git', 'cat-file', '-t', sha]).stdout.strip(), 'commit')
        for t in tasks['task']:                                                     # every blocked task the state document names is really blocked
            if t['status'] == 'blocked': self.assertIn(t['id'], rd('STATE.md') + rd('TASKS.md'))
        pend = [d['id'] for d in decs['decision'] if d['status'] == 'PROPOSED']
        for d in pend: self.assertIn(d, rd('HANDOFF.md') + rd('STATE.md'), d)      # no pending proposal is invisible to the next agent

    def test_red_actions_stay_denied_and_forbidden_ones_forbidden(self):
        for action, code in (('publish', 20), ('privileged-or-mount', 20), ('device-write-boot', 20), ('delete-or-overwrite', 20), ('write-protected-partitions', 30), ('docs-write', 0)):
            self.assertEqual(self.gov('gate', action).returncode, code, action)

    def test_resume_drill_after_an_interruption(self):
        c = tg.make_clone(tempfile.mkdtemp(prefix='gov-resume.', dir=self.tmp))                      # its own clone: this test changes state
        g = lambda *a: self.gov(*a, cwd=c); git = lambda *a: self.sh(['git', '-c', 'commit.gpgsign=false'] + list(a), cwd=c)
        tp = os.path.join(c, 'governance', 'data', 'tasks.toml')
        tg.mutate(tp, 'task', 'T-0009', 'status', '"in_progress"'); tg.mutate(tp, 'task', 'T-0009', 'resume', '"Paso 3 de 5: falta aplicar 0332 sobre la rama; ver el checkpoint."')
        open(os.path.join(c, 'governance', 'checkpoints', '2026-11-13-T-0009-01.md'), 'w').write('# Checkpoint T-0009 #01\n- Siguiente paso exacto: aplicar 0332 con ci_check.\n')
        self.assertEqual(g('render').returncode, 0); self.assertEqual(g('check').returncode, 0)
        self.assertEqual(git('add', '-A').returncode, 0); self.assertEqual(git('commit', '-q', '-m', 'simulacro: T-0009 en curso').returncode, 0)
        r = g('next'); self.assertEqual(r.returncode, 0); self.assertIn('REANUDAR T-0009', r.stdout)                         # a brand-new process resumes it
        self.assertIn('Paso 3 de 5', open(os.path.join(c, 'governance', 'ACTIVE_TASK.md'), encoding='utf-8').read())
        self.assertIn('T-0009', g('status').stdout)
        tg.mutate(tp, 'task', 'T-0009', 'status', '"done"'); g('render'); r = g('next'); self.assertIn('EMPEZAR T-0008', r.stdout)  # finished: the next one is offered
        self.assertEqual(g('check').returncode, 0)

    def test_the_cold_start_drill_is_self_consistent(self):
        p = self.sh([sys.executable, '-I', DRILL, '--root', self.c, 'prompt']).stdout; self.assertEqual(len(re.findall(r'^\s+q\d+:', p, re.M)), 10)
        for forbidden in ('26a39560', 'T-0009', 'herolte-drop-v2', 'T-0008'): self.assertNotIn(forbidden, p)                         # the statement must not leak the answers
        exp = drill.expected(self.c)
        ans = {'q1': exp['q1'][0], 'q2': 'el árbol wardevsa-ios-a5xelte, cambios del responsable', 'q3': '%s con python3 tools/governance.py next' % exp['q3'][0], 'q4': exp['q4'], 'q5': exp['q5'],
               'q6': {'level': 'L2', 'domain': 'host', 'booted_on_phone': False}, 'q7': exp['q7'][0], 'q8': '5 errores, documentados en KNOWN_ISSUES.md',
               'q9': 'python3 tools/governance.py next; ver ACTIVE_TASK.md', 'q10': 'el director; no son una autorización'}
        f = os.path.join(self.tmp, 'ok.json'); json.dump(ans, open(f, 'w')); r = self.sh([sys.executable, '-I', DRILL, '--root', self.c, 'grade', f]); self.assertEqual(r.returncode, 0, r.stdout)
        for key, wrong in (('q1', 'main'), ('q3', 'T-0004'), ('q4', ['T-0008']), ('q5', {'publish': 'A'}), ('q6', {'level': 'L3', 'domain': 'host', 'booted_on_phone': True}), ('q7', 'deadbeef0000'), ('q8', '0')):
            bad = dict(ans); bad[key] = wrong; json.dump(bad, open(f, 'w')); self.assertEqual(self.sh([sys.executable, '-I', DRILL, '--root', self.c, 'grade', f]).returncode, 1, key)
        json.dump({}, open(f, 'w')); self.assertEqual(self.sh([sys.executable, '-I', DRILL, '--root', self.c, 'grade', f]).returncode, 1)
        open(f, 'w').write('no es json'); self.assertEqual(self.sh([sys.executable, '-I', DRILL, '--root', self.c, 'grade', f]).returncode, 2)

    def test_the_drill_never_writes(self):
        before = tg.snapshot(self.c)
        for a in (['prompt'], ['expected'], ['expected', '--json']): self.assertEqual(self.sh([sys.executable, '-I', DRILL, '--root', self.c] + a).returncode, 0)
        self.assertEqual(tg.snapshot(self.c), before)


if __name__ == '__main__':
    unittest.main(verbosity=1)
