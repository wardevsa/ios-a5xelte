#!/usr/bin/env python3
"""Mutation battery for tools/governance.py: each mutant disables ONE rule in a throw-away `git clone --shared` of this repository (with the current work-tree files overlaid)
and runs tools/test_governance.py; a mutant is DETECTED when that suite fails. The repository itself is never modified. If governance.py changes so that a mutation no longer
applies, this script fails loudly (the assertion), which is the cue to update the mutants.
    python3 tools/governance_mutation.py [--out RESULT.txt] [--jobs 5]"""
import argparse, os, shutil, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ap = argparse.ArgumentParser(); ap.add_argument('--out'); ap.add_argument('--jobs', type=int, default=5); A = ap.parse_args()
M = tempfile.mkdtemp(prefix='gov-mutants.')
MUT=[
('M01-git-optional-locks',"['git', '--no-optional-locks', '-C', root, *args]","['git', '-C', root, *args]"),
('M02-render-overwrites-handwritten',"if not open(p, encoding='utf-8').read().startswith(GENERATED): raise DataError(","if False: raise DataError("),
('M03-unknown-action-green',"tier = acts.get(a, {}).get('tier', 'X')","tier = acts.get(a, {}).get('tier', 'A')"),
('M04-authorization-ignores-action',"if action not in lst(d.get('authorizes')): return False,","if False: return False,"),
('M05-yellow-done-without-review',"        if t.get('status') == 'done':\n            for a in [a for a in lst(t.get('actions')) if actions.get(a, {}).get('tier') == 'B']:","        if False:\n            for a in [a for a in lst(t.get('actions')) if actions.get(a, {}).get('tier') == 'B']:"),
('M06-next-ignores-owner',"if t.get('status') != 'ready' or t.get('owner') != 'ingeniero' or t.get('blocked_on'): continue","if t.get('status') != 'ready' or t.get('blocked_on'): continue"),
('M07-next-ignores-dependencies',"        if any(tk.get(d, {}).get('status') != 'done' for d in lst(t.get('depends_on'))): continue\n        if dec is not None","        if dec is not None"),
('M08-evidence-always-ok',"if sha256_file(p) == h: note('OK'","if True: note('OK'"),
('M09-regress-ignores-tree-change',"if before is not None and tree_fingerprint(root) != before:","if False:"),
('M10-screen-allows-everything',"if exe in FORBIDDEN_EXEC: pr.append(","if False: pr.append("),
('M11-no-policy-pin',"if pin.get('sha256') != phash: E(","if False: E("),
('M12-host-may-claim-hardware',"if dm == 'host' and level_num(lv) > 2: E('%s: una prueba host","if False: E('%s: una prueba host"),
('M13-render-not-atomic',"        os.replace(tmp, p)\n","        open(p, 'w', encoding='utf-8').write(text); os.replace(tmp, tmp) if False else None\n"),
('M14-empty-containers-pass',"if not (isinstance(v, list) and v and all(isinstance(x, dict) for x in v)): E(","if False: E("),
('M15-gate-red-without-task-allowed',"if task is None: print('DENEGADA %s (rojo): sin --task no hay autorización registrada que consultar' % action); return 20","if task is None: print('PERMITIDA'); return 0"),
('M16-min-evidence-ignored',"if me is not None and t.get('status') in ('in_review', 'done'):","if False:"),
('M17-done-with-open-dependency',"if t.get('status') == 'done': E('%s: done con dependencia %s sin terminar' % (i, dep))","if False: E('%s: done con dependencia %s sin terminar' % (i, dep))"),
('M18-symlink-evidence-accepted',"if os.path.islink(p): note('SYMLINK'","if False: note('SYMLINK'"),
('M19-evidence-strict-ignored',"return 1 if bad or (strict and unverified) else 0","return 1 if bad else 0"),
('M20-authorization-ignores-director',"if d.get('approved_by') != role_ok: return False,","if False: return False,"),
('M21-in-progress-resume-ignored',"    if act: return sorted(act, key=lambda t: (t.get('priority', 99) if isinstance(t.get('priority'), int) else 99, t.get('id')))[0], 'resume'","    if False: pass"),
('M22-check-writes-state',"def check(root, use_git=True, strict=False):\n","def check(root, use_git=True, strict=False):\n    open(os.path.join(root, 'governance', 'ESCRITO_POR_CHECK'), 'w').write('x')\n"),
]
def mk(name, old, new):
    d = '%s/%s' % (M, name); subprocess.run(['git', 'clone', '-q', '--shared', REPO, d], check=True, capture_output=True)
    for rel in ('governance', 'tools', 'AGENTS.md'):
        s, t = '%s/%s' % (REPO, rel), '%s/%s' % (d, rel)
        if os.path.isdir(s): shutil.rmtree(t, ignore_errors=True); shutil.copytree(s, t, ignore=shutil.ignore_patterns('__pycache__'))
        else: shutil.copy(s, t)
    g = open('%s/tools/governance.py' % d).read(); assert g.count(old) == 1 or name == 'M00-control', (name, g.count(old)); open('%s/tools/governance.py' % d, 'w').write(g.replace(old, new) if old else g)
    r = subprocess.run([sys.executable, '-W', 'ignore', 'tools/test_governance.py'], cwd=d, capture_output=True, text=True, timeout=900)
    fails = [l.split(' (')[0].replace('FAIL: ', '').replace('ERROR: ', '') for l in (r.stdout + r.stderr).splitlines() if l.startswith(('FAIL:', 'ERROR:'))]
    return name, r.returncode, fails
try:
    ctl = mk('M00-control', '', '')                                                  # the UNMUTATED clone must pass, otherwise every mutant would look "detected"
    if ctl[1] != 0: print('CONTROL SIN MUTAR FALLA (%s): la batería no es válida hasta que pase' % ', '.join(ctl[2])); sys.exit(2)
    with ThreadPoolExecutor(A.jobs) as ex: res = list(ex.map(lambda m: mk(*m), MUT))
    out = ['%-38s CONTROL sin mutar: pasa (0 fallos)' % 'M00-control']
    out += ['%-38s %s  (%d pruebas fallan)%s' % (n, 'DETECTADO' if rc != 0 else 'SOBREVIVE !!', len(f), '  p.ej. ' + f[0] if f else '') for n, rc, f in res]
    out.append('TOTAL: %d mutantes, %d detectados, %d sobreviven' % (len(res), sum(1 for r in res if r[1] != 0), sum(1 for r in res if r[1] == 0)))
    print('\n'.join(out))
    if A.out: open(A.out, 'x').write('\n'.join(out) + '\n')                    # 'x': never overwrites an existing result
    sys.exit(1 if any(r[1] == 0 for r in res) else 0)
finally: shutil.rmtree(M, ignore_errors=True)                                      # only the throw-away clones this script created
