#!/usr/bin/env python3
"""IOS S7 governance tool: validates the governance data, renders its views, answers "may I do this?", picks the next task,
verifies evidence hashes and runs the regression suites. Read-only on the repository except `render`, which writes the generated views.

  python3 tools/governance.py check               validate everything (exit 0 = no errors; warnings do not fail)
  python3 tools/governance.py render [--check]    regenerate TASKS/ACTIVE_TASK/DECISIONS/EVIDENCE.md (with --check: fail if out of date)
  python3 tools/governance.py can ACTION          policy lookup; exit 0 = tier A (autonomous), 10 = B (review before consolidating),
                                                  20 = C (explicit authorization of the Director), 30 = X (forbidden), 2 = unknown action
  python3 tools/governance.py next                the next task an engineer may start without asking anyone
  python3 tools/governance.py status              one-page picture: git, active task, blockers, pending decisions
  python3 tools/governance.py evidence [--all]    verify the SHA-256 of indexed artifacts (missing files are SKIP, not failures)
  python3 tools/governance.py regress [--suite ID] [--list]   run the regression suites (missing prerequisites are SKIP)
Options: --root DIR (repository root, default: parent of tools/), --no-git (skip checks that need git; used by the tests).
Data lives in governance/data/*.toml (source of truth); the .md views are generated from it and must not be edited by hand."""
import argparse, hashlib, os, re, subprocess, sys, time, tomllib

TIER_ORDER = {'A': 0, 'B': 1, 'C': 2, 'X': 3}
EXIT_BY_TIER = {'A': 0, 'B': 10, 'C': 20, 'X': 30}
REQUIRED_DOCS = ['README.md', 'CONSTITUTION.md', 'AUTHORITY.md', 'AUTONOMY_POLICY.md', 'SECURITY_POLICY.md', 'ARCHITECTURE.md', 'ROADMAP.md', 'STATE.md',
                 'HANDOFF.md', 'TASKS.md', 'ACTIVE_TASK.md', 'DECISIONS.md', 'EVIDENCE.md']
REQUIRED_DATA = ['policy.toml', 'tasks.toml', 'decisions.toml', 'evidence.toml', 'regression.toml']
TASK_STATUS = {'ready', 'blocked', 'in_progress', 'in_review', 'done', 'cancelled'}
DECISION_STATUS = {'PROPOSED', 'APPROVED', 'REJECTED', 'SUPERSEDED'}
DECISION_SCOPE = {'architecture', 'policy', 'process', 'operation', 'priority'}
GENERATED = '<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->\n'


def load(root, name):
    with open(os.path.join(root, 'governance', 'data', name), 'rb') as f:
        return tomllib.load(f)


def git(root, *args):
    r = subprocess.run(['git', '-C', root, *args], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def tier_of_actions(policy, actions):
    acts = {a['id']: a for a in policy.get('actions', [])}
    t = 'A'
    for a in actions:
        if a in acts and TIER_ORDER[acts[a]['tier']] > TIER_ORDER[t]: t = acts[a]['tier']
    return t


# ----------------------------------------------------------------------------------------------------------------------------------- check
def check(root, use_git=True):
    errs, warns = [], []
    E = errs.append; W = warns.append
    gov = os.path.join(root, 'governance')
    for d in REQUIRED_DOCS:
        if not os.path.isfile(os.path.join(gov, d)): E('falta governance/%s' % d)
    for d in REQUIRED_DATA:
        if not os.path.isfile(os.path.join(gov, 'data', d)): E('falta governance/data/%s' % d)
    if errs: return errs, warns
    try:
        policy, tasks, decs = load(root, 'policy.toml'), load(root, 'tasks.toml'), load(root, 'decisions.toml')
        evid, reg = load(root, 'evidence.toml'), load(root, 'regression.toml')
    except tomllib.TOMLDecodeError as e:
        return ['TOML inválido: %s' % e], warns
    roles = policy.get('roles', {})
    for r in ('director', 'jefe-tecnico', 'ingeniero'):
        if r not in roles: E('policy.toml: falta el rol %s' % r)
    if set(policy.get('tiers', {})) != set(TIER_ORDER): E('policy.toml: los niveles deben ser exactamente A, B, C, X')
    actions = {}
    for a in policy.get('actions', []):
        if a.get('id') in actions: E('policy.toml: acción duplicada %s' % a.get('id'))
        actions[a.get('id')] = a
        if a.get('tier') not in TIER_ORDER: E('policy.toml: acción %s con nivel inválido %r' % (a.get('id'), a.get('tier')))
        if not a.get('summary'): E('policy.toml: acción %s sin resumen' % a.get('id'))
        if a.get('tier') == 'C' and a.get('authorizer') != 'director': E('policy.toml: la acción C %s debe exigir al director' % a.get('id'))
        if a.get('tier') == 'B' and a.get('reviewer') not in ('jefe-tecnico', 'director'): E('policy.toml: la acción B %s debe nombrar revisor' % a.get('id'))
    # decisions
    dec = {}
    for d in decs.get('decision', []):
        i = d.get('id', '?')
        if not re.fullmatch(r'D-\d{4}', i): E('decisión con id inválido %r' % i)
        if i in dec: E('decisión duplicada %s' % i)
        dec[i] = d
        if d.get('status') not in DECISION_STATUS: E('%s: estado inválido %r' % (i, d.get('status')))
        if d.get('scope') not in DECISION_SCOPE: E('%s: ámbito inválido %r' % (i, d.get('scope')))
        for k in ('title', 'date', 'proposer', 'rationale', 'reversal'):
            if not d.get(k): E('%s: falta %s' % (i, k))
        if d.get('proposer') not in roles: E('%s: proponente desconocido %r' % (i, d.get('proposer')))
        if d.get('status') == 'APPROVED':
            ab = d.get('approved_by')
            if ab not in roles: E('%s: APPROVED sin aprobador válido' % i)
            else:
                can = roles[ab].get('can_approve', [])
                if d.get('scope') not in can: E('%s: el rol %s no puede aprobar decisiones de ámbito %s' % (i, ab, d.get('scope')))
                if ab == d.get('proposer') == 'ingeniero': E('%s: el ingeniero no aprueba sus propias propuestas' % i)
            for k in ('approval_date', 'approval_ref'):
                if not d.get(k): E('%s: APPROVED sin %s' % (i, k))
        elif d.get('approved_by'): E('%s: tiene aprobador pero estado %s' % (i, d.get('status')))
    for i, d in dec.items():
        for s in d.get('supersedes', []):
            if s not in dec: E('%s supersede una decisión inexistente %s' % (i, s))
    # evidence
    ev = {}
    for e in evid.get('evidence', []):
        i = e.get('id', '?')
        if not re.fullmatch(r'E-\d{4}', i): E('evidencia con id inválido %r' % i)
        if i in ev: E('evidencia duplicada %s' % i)
        ev[i] = e
        for k in ('title', 'kind', 'path', 'location', 'created'):
            if not e.get(k): E('%s: falta %s' % (i, k))
        if e.get('immutable') and not re.fullmatch(r'[0-9a-f]{64}', e.get('sha256', '')): E('%s: evidencia inmutable sin SHA-256 válido' % i)
        if e.get('sha256') and not re.fullmatch(r'[0-9a-f]{64}', e['sha256']): E('%s: SHA-256 mal formado' % i)
    # tasks
    tk = {}
    for t in tasks.get('task', []):
        i = t.get('id', '?')
        if not re.fullmatch(r'T-\d{4}', i): E('tarea con id inválido %r' % i)
        if i in tk: E('tarea duplicada %s' % i)
        tk[i] = t
        if t.get('status') not in TASK_STATUS: E('%s: estado inválido %r' % (i, t.get('status')))
        for k in ('title', 'priority', 'owner', 'acceptance', 'actions'):
            if k not in t or t[k] in ('', None): E('%s: falta %s' % (i, k))
        for a in t.get('actions', []):
            if a not in actions: E('%s: acción desconocida %r' % (i, a))
        for x in t.get('evidence', []):
            if x not in ev: E('%s: evidencia inexistente %s' % (i, x))
        if t.get('status') == 'blocked' and not t.get('blocked_on'): E('%s: bloqueada sin blocked_on' % i)
        tier = tier_of_actions(policy, t.get('actions', []))
        if tier == 'X' and t.get('status') not in ('cancelled',): E('%s: contiene una acción prohibida (X)' % i)
        if tier == 'C' and t.get('status') in ('in_progress', 'in_review', 'done'):
            ref = t.get('authorization_ref')
            if ref not in dec: E('%s: acción C en curso/hecha sin authorization_ref a una decisión' % i)
            else:
                d = dec[ref]
                if not (d.get('status') == 'APPROVED' and d.get('approved_by') == 'director'): E('%s: authorization_ref %s no es una decisión APPROVED del director' % (i, ref))
    for i, t in tk.items():
        for dep in t.get('depends_on', []):
            if dep not in tk: E('%s: depende de una tarea inexistente %s' % (i, dep))
            elif tk[dep].get('status') != 'done':
                if t.get('status') == 'done': E('%s: done con dependencia %s sin terminar' % (i, dep))
                elif t.get('status') == 'in_progress': E('%s: en curso pero su dependencia %s no está done' % (i, dep))   # in_review may wait on dependencies
    # cycles
    state = {}
    def dfs(n, path):
        state[n] = 1
        for m in tk.get(n, {}).get('depends_on', []):
            if m not in tk: continue
            if state.get(m) == 1: E('ciclo de dependencias: %s' % ' -> '.join(path + [n, m]))
            elif m not in state: dfs(m, path + [n])
        state[n] = 2
    for n in tk:
        if n not in state: dfs(n, [])
    active = [i for i, t in tk.items() if t.get('status') == 'in_progress']
    if len(active) > 1: E('más de una tarea en curso: %s' % ', '.join(active))
    # regression
    suites = {}
    for s in reg.get('suite', []):
        i = s.get('id', '?')
        if i in suites: E('suite duplicada %s' % i)
        suites[i] = s
        for k in ('title', 'command', 'baseline'):
            if not s.get(k): E('suite %s: falta %s' % (i, k))
    # views up to date
    for fn, want in render_all(root).items():
        p = os.path.join(gov, fn)
        have = open(p, encoding='utf-8').read() if os.path.isfile(p) else ''
        if have != want: E('governance/%s está desactualizado: ejecuta `python3 tools/governance.py render`' % fn)
    # links in the hand-written docs
    for fn in REQUIRED_DOCS:
        p = os.path.join(gov, fn)
        for m in re.finditer(r'\]\(([^)#\s]+)(?:#[^)]*)?\)', open(p, encoding='utf-8').read()):
            tgt = m.group(1)
            if re.match(r'^[a-z]+:', tgt): continue
            if not os.path.exists(os.path.normpath(os.path.join(gov, tgt))): E('governance/%s: enlace roto -> %s' % (fn, tgt))
    ag = os.path.join(root, 'AGENTS.md')
    if not os.path.isfile(ag) or 'governance/README.md' not in open(ag, encoding='utf-8').read(): E('AGENTS.md no apunta a governance/README.md')
    # STATE.md commit
    st = open(os.path.join(gov, 'STATE.md'), encoding='utf-8').read()
    m = re.search(r'<!-- state-commit: ([0-9a-f]{7,40}) -->', st)
    if not m: E('STATE.md sin la marca <!-- state-commit: SHA -->')
    elif use_git:
        rc, _ = git(root, 'cat-file', '-e', m.group(1) + '^{commit}')
        if rc != 0: E('STATE.md: el commit %s no existe en este repositorio' % m.group(1))
        else:
            rc, _ = git(root, 'merge-base', '--is-ancestor', m.group(1), 'HEAD')
            if rc != 0: E('STATE.md: el commit %s no es ancestro de HEAD' % m.group(1))
            else:
                rc, n = git(root, 'rev-list', '--count', m.group(1) + '..HEAD')
                if rc == 0 and n != '0': W('STATE.md describe el commit %s; HEAD lleva %s commit(s) más: revisar si el estado sigue vigente' % (m.group(1)[:8], n))
    return errs, warns


# --------------------------------------------------------------------------------------------------------------------------------- render
def esc(s): return str(s).replace('|', '\\|').replace('\n', ' ')


def render_all(root):
    policy, tasks, decs = load(root, 'policy.toml'), load(root, 'tasks.toml'), load(root, 'decisions.toml')
    evid = load(root, 'evidence.toml')
    tk = sorted(tasks.get('task', []), key=lambda t: (t.get('priority', 99), t.get('id', '')))
    out = {}
    L = [GENERATED, '# Cola de tareas\n', 'Ordenada por prioridad (1 = la más urgente). "Nivel" = el más alto de sus acciones (`policy.toml`): **A** autónomo, **B** revisión antes de consolidar, **C** autorización explícita del Director, **X** prohibido.\n',
         '| ID | Estado | Prio | Título | Depende de | Nivel | Bloqueo |', '|---|---|---|---|---|---|---|']
    for t in tk:
        L.append('| %s | %s | %s | %s | %s | %s | %s |' % (t['id'], t['status'], t.get('priority', ''), esc(t['title']), ', '.join(t.get('depends_on', [])) or '—',
                                                      tier_of_actions(policy, t.get('actions', [])), esc(t.get('blocked_on', '')) or '—'))
    L += ['', '## Criterios de aceptación\n']
    for t in tk:
        L.append('- **%s** %s: %s' % (t['id'], esc(t['title']), esc(t.get('acceptance', ''))))
    out['TASKS.md'] = '\n'.join(L) + '\n'

    active = [t for t in tk if t['status'] == 'in_progress']
    A = [GENERATED, '# Tarea activa\n']
    if active:
        t = active[0]
        A += ['**%s — %s**\n' % (t['id'], t['title']), '- Estado: `in_progress`  - Nivel: %s' % tier_of_actions(policy, t.get('actions', [])),
              '- Acciones: %s' % ', '.join(t.get('actions', [])), '- Depende de: %s' % (', '.join(t.get('depends_on', [])) or '—'),
              '- Aceptación: %s' % t.get('acceptance', ''), '- Notas de reanudación: %s' % (t.get('resume', '—') or '—')]
    else:
        nxt = next_task(policy, tasks)
        A += ['**No hay ninguna tarea en curso.**\n', 'Tareas pendientes de revisión: %s' % (', '.join('%s (%s)' % (t['id'], t['title']) for t in tk if t['status'] == 'in_review') or '—'), '',
              'Siguiente tarea que se puede empezar sin pedir autorización: %s' % ('**%s — %s**' % (nxt['id'], nxt['title']) if nxt else '— (todo bloqueado: ver `TASKS.md`)')]
    A += ['', '## Cómo reanudar', '1. Lee `README.md` y `HANDOFF.md`; ejecuta `python3 tools/governance.py check` y `status`.', '2. Si hay tarea en curso, sigue su campo `resume` y el último fichero de `checkpoints/`.',
          '3. Si no la hay, toma la que indique `python3 tools/governance.py next`, márcala `in_progress` en `data/tasks.toml`, ejecuta `render` y anota el primer checkpoint.']
    out['ACTIVE_TASK.md'] = '\n'.join(A) + '\n'

    D = [GENERATED, '# Registro de decisiones\n', 'Estados: `PROPOSED` (propuesta, **sin efecto**), `APPROVED` (aprobada por quien tiene autoridad para ese ámbito, con referencia), `REJECTED`, `SUPERSEDED`. Una propuesta del ingeniero **no es una decisión aprobada**.\n',
         '| ID | Estado | Ámbito | Fecha | Título | Propone | Aprueba | Referencia |', '|---|---|---|---|---|---|---|---|']
    ds = sorted(decs.get('decision', []), key=lambda d: d['id'])
    for d in ds:
        D.append('| %s | %s | %s | %s | %s | %s | %s | %s |' % (d['id'], d['status'], d['scope'], d['date'], esc(d['title']), d['proposer'], d.get('approved_by', '—'), esc(d.get('approval_ref', '—'))))
    D.append('')
    for d in ds:
        D += ['## %s — %s' % (d['id'], d['title']), '- **Estado:** %s%s' % (d['status'], ' (%s, %s)' % (d.get('approved_by'), d.get('approval_date')) if d['status'] == 'APPROVED' else ''),
              '- **Razón:** %s' % d['rationale'], '- **Consecuencias:** %s' % d.get('consequences', '—'), '- **Cómo se revierte:** %s' % d['reversal']]
        if d.get('supersedes'): D.append('- **Sustituye a:** %s' % ', '.join(d['supersedes']))
        D.append('')
    out['DECISIONS.md'] = '\n'.join(D) + '\n'

    V = [GENERATED, '# Índice de evidencias\n', 'Evidencia = artefacto cuyo hash respalda una afirmación. Las **inmutables** no se editan, mueven ni borran; se añaden versiones nuevas con otro nombre. Verificar: `python3 tools/governance.py evidence [--all]`.\n',
         '| ID | Tipo | Título | Ubicación | Ruta | SHA-256 | Inmutable |', '|---|---|---|---|---|---|---|']
    for e in sorted(evid.get('evidence', []), key=lambda e: e['id']):
        V.append('| %s | %s | %s | %s | `%s` | `%s` | %s |' % (e['id'], e['kind'], esc(e['title']), e['location'], e['path'], (e.get('sha256') or '—')[:16] + ('…' if e.get('sha256') else ''), 'sí' if e.get('immutable') else 'no'))
    out['EVIDENCE.md'] = '\n'.join(V) + '\n'
    return out


def next_task(policy, tasks):
    tk = {t['id']: t for t in tasks.get('task', [])}
    cands = []
    for t in tk.values():
        if t['status'] != 'ready': continue
        if any(tk.get(d, {}).get('status') != 'done' for d in t.get('depends_on', [])): continue
        if tier_of_actions(policy, t.get('actions', [])) in ('C', 'X'): continue
        cands.append(t)
    cands.sort(key=lambda t: (t.get('priority', 99), t['id']))
    return cands[0] if cands else None


# ------------------------------------------------------------------------------------------------------------------------------ commands
def cmd_render(root, check_only):
    bad = 0
    for fn, text in render_all(root).items():
        p = os.path.join(root, 'governance', fn)
        have = open(p, encoding='utf-8').read() if os.path.isfile(p) else None
        if have == text: continue
        if check_only: print('DESACTUALIZADO governance/%s' % fn); bad += 1
        else: open(p, 'w', encoding='utf-8').write(text); print('escrito governance/%s' % fn)
    return 1 if bad else 0


def cmd_can(root, action):
    policy = load(root, 'policy.toml'); a = {x['id']: x for x in policy['actions']}.get(action)
    if not a:
        print('acción desconocida: %s\nacciones: %s' % (action, ', '.join(sorted(x['id'] for x in policy['actions'])))); return 2
    t = a['tier']; name = policy['tiers'][t]['name']
    print('%s: nivel %s (%s)\n  %s' % (action, t, name, a['summary']))
    if a.get('requires'): print('  condiciones: ' + '; '.join(a['requires']))
    if t == 'B': print('  revisor antes de consolidar: %s' % a['reviewer'])
    if t == 'C': print('  autoriza: %s, de forma explícita, acotada y registrada en decisions.toml' % a['authorizer'])
    if t == 'X': print('  prohibida por regla del proyecto; solo el Director puede cambiarla modificando AGENTS.md y policy.toml')
    return EXIT_BY_TIER[t]


def cmd_next(root):
    n = next_task(load(root, 'policy.toml'), load(root, 'tasks.toml'))
    if not n: print('ninguna tarea autónoma disponible: todo está bloqueado o necesita autorización (ver governance/TASKS.md)'); return 1
    print('%s  %s\n  aceptación: %s' % (n['id'], n['title'], n['acceptance'])); return 0


def cmd_status(root, use_git=True):
    policy, tasks, decs = load(root, 'policy.toml'), load(root, 'tasks.toml'), load(root, 'decisions.toml')
    print('raíz: %s' % root)
    if use_git:
        _, br = git(root, 'branch', '--show-current'); _, head = git(root, 'log', '--oneline', '-1'); _, dirty = git(root, 'status', '--porcelain')
        print('rama: %s\nHEAD: %s\nsin confirmar: %d fichero(s)' % (br, head, len([l for l in dirty.splitlines() if l])))
        _, wt = git(root, 'worktree', 'list')
        if wt.count('\n'): print('worktrees:\n  ' + wt.replace('\n', '\n  '))
    tk = tasks.get('task', []); by = {}
    for t in tk: by[t['status']] = by.get(t['status'], 0) + 1
    print('tareas: ' + ', '.join('%s=%d' % kv for kv in sorted(by.items())))
    act = [t for t in tk if t['status'] == 'in_progress']
    print('en curso: %s' % (', '.join('%s %s' % (t['id'], t['title']) for t in act) or 'ninguna'))
    n = next_task(policy, tasks); print('siguiente autónoma: %s' % (('%s %s' % (n['id'], n['title'])) if n else 'ninguna'))
    pend = [d for d in decs.get('decision', []) if d['status'] == 'PROPOSED']
    print('decisiones PROPOSED sin aprobar: %d (%s)' % (len(pend), ', '.join(d['id'] for d in pend)))
    print('bloqueadas: ' + '; '.join('%s [%s]' % (t['id'], t['blocked_on']) for t in tk if t['status'] == 'blocked'))
    return 0


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
    return h.hexdigest()


def cmd_evidence(root, all_):
    evid = load(root, 'evidence.toml'); ok = bad = skip = 0
    for e in sorted(evid.get('evidence', []), key=lambda e: e['id']):
        p = os.path.expanduser(e['path']) if e['path'].startswith('~') else (e['path'] if os.path.isabs(e['path']) else os.path.join(root, e['path']))
        if not e.get('sha256'): print('SKIP %s sin hash (%s)' % (e['id'], e['title'])); skip += 1; continue
        if not os.path.isfile(p): print('SKIP %s no existe en esta máquina: %s' % (e['id'], e['path'])); skip += 1; continue
        if os.path.getsize(p) > (1 << 30) and not all_: print('SKIP %s mayor de 1 GiB (usa --all)' % e['id']); skip += 1; continue
        if sha256_file(p) == e['sha256']: print('OK   %s %s' % (e['id'], e['title'])); ok += 1
        else: print('FALLA %s %s: el hash NO coincide' % (e['id'], e['path'])); bad += 1
    print('RESUMEN evidencias: %d OK, %d FALLA, %d SKIP' % (ok, bad, skip)); return 1 if bad else 0


def cmd_regress(root, suite, list_only):
    reg = load(root, 'regression.toml'); rows = []; failed = 0
    for s in reg.get('suite', []):
        if suite and s['id'] != suite: continue
        if list_only: print('%-22s %-9s %s\n    baseline: %s' % (s['id'], s.get('cost', ''), s['title'], s['baseline'])); continue
        miss = [r for r in s.get('requires', []) if not os.path.exists(os.path.expanduser(r) if r.startswith('~') else os.path.join(root, r))]
        if miss: rows.append((s['id'], 'SKIP', 'falta: ' + ', '.join(miss), 0)); continue
        t0 = time.time(); cwd = os.path.join(root, s['cwd']) if s.get('cwd') else root
        r = subprocess.run([os.path.expanduser(x) if x.startswith('~') else x for x in s['command']], cwd=cwd, capture_output=True, text=True, timeout=s.get('timeout', 900))
        tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or ['']
        known = bool(s.get('known_failing'))
        st = ('PASS' if r.returncode == 0 else 'FALLA') if not known else ('XPASS' if r.returncode == 0 else 'XFAIL')
        rows.append((s['id'], st, tail[0][:110], time.time() - t0)); failed += (st == 'FALLA')
    if list_only: return 0
    for i, st, msg, dt in rows: print('%-5s %-22s %5.1fs  %s' % (st, i, dt, msg))
    print('RESUMEN regresión: %d PASS, %d FALLA, %d SKIP, %d XFAIL (deuda conocida), %d XPASS (revisar known_failing)' % (sum(r[1] == 'PASS' for r in rows), failed,
          sum(r[1] == 'SKIP' for r in rows), sum(r[1] == 'XFAIL' for r in rows), sum(r[1] == 'XPASS' for r in rows)))
    return 1 if failed else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); ap.add_argument('--no-git', action='store_true')
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('check'); p = sub.add_parser('render'); p.add_argument('--check', action='store_true')
    p = sub.add_parser('can'); p.add_argument('action'); sub.add_parser('next'); sub.add_parser('status')
    p = sub.add_parser('evidence'); p.add_argument('--all', action='store_true')
    p = sub.add_parser('regress'); p.add_argument('--suite'); p.add_argument('--list', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'check':
        errs, warns = check(a.root, not a.no_git)
        for w in warns: print('AVISO  ' + w)
        for e in errs: print('ERROR  ' + e)
        print('RESUMEN gobierno: %d error(es), %d aviso(s)' % (len(errs), len(warns))); return 1 if errs else 0
    if a.cmd == 'render': return cmd_render(a.root, a.check)
    if a.cmd == 'can': return cmd_can(a.root, a.action)
    if a.cmd == 'next': return cmd_next(a.root)
    if a.cmd == 'status': return cmd_status(a.root, not a.no_git)
    if a.cmd == 'evidence': return cmd_evidence(a.root, a.all)
    if a.cmd == 'regress': return cmd_regress(a.root, a.suite, a.list)


if __name__ == '__main__':
    sys.exit(main())
