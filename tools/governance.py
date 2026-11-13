#!/usr/bin/env python3
"""IOS S7 governance tool. It ENFORCES the autonomy policy where it can (gate, task selection, validation) and never grants authority.

READ-ONLY commands (they never write files, never change Git state, never execute project code):
  check [--strict]            validate the governance data, views, links, policy pin and STATE anchor (exit 0 = no errors)
  render --check              are the generated views up to date?
  can ACTION                  policy lookup: tier and colour (exit 0 green, 10 yellow, 20 red, 30 forbidden, 2 unknown)
  gate ACTION [--task T] [--consolidate]   would a RECORDED authorization/review allow this action now? (see below)
  next                        the task an engineer may start (or resume) without asking anyone
  status                      git + queue picture
  evidence [--all] [--strict] verify indexed artifacts against their SHA-256 and size
WRITING command (writes ONLY the four generated views, atomically, and refuses to overwrite a file that is not generated):
  render
RUNNING command (runs the regression suites declared in data/regression.toml after a safety screen; fails a suite that alters the Git tree):
  regress [--suite ID] [--list] [--strict]

Colours: A = green (autonomous), B = yellow (implement locally, review before consolidating), C = red (needs the Director's recorded authorization),
X = red/forbidden. NO automatic check in this tool is an authorization: `can`, `gate`, `check` and `status` only REPORT; none of them executes the action.
gate exit codes: 0 allowed (green) | 10 yellow: allowed locally, not consolidated | 11 yellow consolidation allowed (valid review recorded) |
                 12 yellow consolidation DENIED | 20 red DENIED (no valid recorded authorization) | 30 forbidden | 2 unknown action.
Options: --root DIR (default: the repository that contains this file; no absolute path is hard-coded), --no-git (skip git; used by tests)."""
import argparse, datetime, hashlib, os, re, subprocess, sys, tempfile, time, tomllib

TIER_ORDER = {'A': 0, 'B': 1, 'C': 2, 'X': 3}
COLOR = {'A': 'verde', 'B': 'amarillo', 'C': 'rojo', 'X': 'rojo (prohibida)'}
EXIT_BY_TIER = {'A': 0, 'B': 10, 'C': 20, 'X': 30}
REQUIRED_DOCS = ['README.md', 'CONSTITUTION.md', 'AUTHORITY.md', 'AUTONOMY_POLICY.md', 'SECURITY_POLICY.md', 'ARCHITECTURE.md', 'ROADMAP.md', 'STATE.md',
                 'HANDOFF.md', 'KNOWN_ISSUES.md', 'AUDIT_GOVERNANCE_TOOL.md', 'ONBOARDING_DRILL.md', 'TASKS.md', 'ACTIVE_TASK.md', 'DECISIONS.md', 'EVIDENCE.md']
GENERATED_VIEWS = ('TASKS.md', 'ACTIVE_TASK.md', 'DECISIONS.md', 'EVIDENCE.md')      # the ONLY files `render` may write
REQUIRED_DATA = ['policy.toml', 'policy.pin.toml', 'tasks.toml', 'decisions.toml', 'evidence.toml', 'regression.toml']
TASK_STATUS = {'ready', 'blocked', 'in_progress', 'in_review', 'done', 'cancelled'}
DECISION_STATUS = {'PROPOSED', 'APPROVED', 'REJECTED', 'SUPERSEDED'}
DECISION_SCOPE = {'architecture', 'policy', 'process', 'operation', 'priority'}
LEVELS = ('L0', 'L1', 'L2', 'L3', 'L4')
DOMAINS = {'host', 'build', 'gpu-device', 'ios-integration', 'device', 'doc'}      # pc tests | compilation | physical GPU | iOS integration | other phone data | documents
DEVICES = {'none', 'this-unit', 'upstream-device'}
GENERATED = '<!-- GENERADO por tools/governance.py render desde governance/data/*.toml. NO EDITAR A MANO: se pierde en el siguiente render. -->\n'
# --- command screen for `regress`: a safety net against mistakes, NOT a sandbox (a suite is arbitrary code the repository owner reviewed)
FORBIDDEN_EXEC = {'sudo', 'su', 'doas', 'pkexec', 'mount', 'umount', 'losetup', 'dd', 'mkfs', 'mkfs.hfsplus', 'mkfs.ext4', 'fsck', 'fsck.hfs', 'fsck_hfs', 'rm', 'rmdir', 'mv', 'shred',
                  'truncate', 'chmod', 'chown', 'adb', 'fastboot', 'curl', 'wget', 'ssh', 'scp', 'rsync', 'nc', 'ncat', 'systemctl', 'kill', 'pkill', 'reboot', 'shutdown', 'gh'}
GIT_READONLY = {'status', 'log', 'diff', 'show', 'rev-parse', 'rev-list', 'ls-files', 'ls-tree', 'cat-file', 'merge-base', 'worktree'}
INTERPRETERS = {'python3', 'python', 'bash'}


class DataError(Exception):
    pass


def load(root, name):
    p = os.path.join(root, 'governance', 'data', name)
    try:
        with open(p, 'rb') as f: return tomllib.load(f)
    except FileNotFoundError: raise DataError('falta governance/data/%s' % name)
    except tomllib.TOMLDecodeError as e: raise DataError('TOML inválido en %s: %s' % (name, e))


def git(root, *args):
    """Read-only git. --no-optional-locks + GIT_OPTIONAL_LOCKS=0 stop `git status` from refreshing (writing) .git/index."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    try:
        r = subprocess.run(['git', '--no-optional-locks', '-C', root, *args], capture_output=True, text=True, timeout=60, env=env)
    except (OSError, subprocess.TimeoutExpired) as e: return 128, str(e)
    return r.returncode, r.stdout.strip()


def tree_fingerprint(root):
    """HEAD + every changed/untracked path (name and status), or None when root is not a git work tree."""
    rc, head = git(root, 'rev-parse', 'HEAD')
    if rc != 0: return None
    rc, st = git(root, 'status', '--porcelain=v1', '-uall')
    return hashlib.sha256((head + '\n' + st).encode()).hexdigest() if rc == 0 else None


def tier_of_actions(policy, actions):
    """Highest tier among the actions. FAIL-CLOSED: an unknown action counts as X, never as A."""
    acts = {a.get('id'): a for a in policy.get('actions', [])}
    t = 'A'
    for a in actions:
        tier = acts.get(a, {}).get('tier', 'X')
        if tier not in TIER_ORDER: tier = 'X'
        if TIER_ORDER[tier] > TIER_ORDER[t]: t = tier
    return t


def lst(x): return x if isinstance(x, list) else []
def level_num(l): return LEVELS.index(l) if l in LEVELS else -1
def today(): return datetime.date.fromisoformat(os.environ.get('GOVERNANCE_TODAY', datetime.date.today().isoformat()))


def decision_ok_for(dec, ref, action, role_ok):
    """Is decision `ref` a valid recorded authorization of `action`? -> (bool, reason)"""
    d = dec.get(ref)
    if d is None: return False, 'la decisión %s no existe' % ref
    if d.get('status') != 'APPROVED': return False, 'la decisión %s no está APPROVED (estado %s)' % (ref, d.get('status'))
    if d.get('approved_by') != role_ok: return False, 'la decisión %s no la aprobó el rol %s' % (ref, role_ok)
    if action not in lst(d.get('authorizes')): return False, 'la decisión %s no autoriza la acción %s (autoriza: %s)' % (ref, action, ', '.join(lst(d.get('authorizes'))) or 'ninguna')
    if d.get('scope') != 'operation': return False, 'la decisión %s no es de ámbito operation' % ref
    vu = d.get('valid_until')
    if vu:
        try:
            if today() > datetime.date.fromisoformat(vu): return False, 'la autorización %s caducó el %s' % (ref, vu)
        except ValueError: return False, 'la decisión %s tiene valid_until inválido' % ref
    return True, 'autorizada por %s (%s)' % (ref, d.get('approval_date'))


def screen_command(root, argv):
    """Problems that make a regression command unacceptable (empty list = acceptable)."""
    pr = []
    if not argv or not all(isinstance(x, str) for x in argv): return ['command debe ser una lista de cadenas']
    exe = os.path.basename(argv[0])
    if exe in FORBIDDEN_EXEC: pr.append('ejecutable prohibido en una suite: %s' % exe)
    if exe == 'git' and (len(argv) < 2 or argv[1] not in GIT_READONLY): pr.append('git solo en modo lectura (%s)' % ', '.join(sorted(GIT_READONLY)))
    if exe in INTERPRETERS:
        rest = argv[1:]; script = None; i = 0
        while i < len(rest):
            a = rest[i]
            if a in ('-c', '-m', '-s') or (a.startswith('-') and 'c' in a[1:] and exe == 'bash'): pr.append('%s no puede usar %s: la suite debe ser un script del repositorio' % (exe, a)); break
            if a == '-W': i += 2; continue
            if a.startswith('-'): i += 1; continue
            script = a; break
        if script is None and not pr: pr.append('%s sin script del repositorio' % exe)
        elif script is not None:
            sp = os.path.normpath(os.path.join(root, script))
            if os.path.isabs(script) or '..' in script.split('/') or not sp.startswith(os.path.realpath(root) + os.sep) and not sp.startswith(os.path.abspath(root) + os.sep): pr.append('el script %s no está dentro del repositorio' % script)
    elif exe not in ('git',) and (os.path.isabs(argv[0]) or '..' in argv[0].split('/')): pr.append('ejecutable fuera del repositorio: %s' % argv[0])
    return pr


# ----------------------------------------------------------------------------------------------------------------------------------- check
def check(root, use_git=True, strict=False):
    """Validate. Any structural surprise (a field with the wrong type...) is reported as an ERROR with exit 1, never as a traceback and never as a pass."""
    try: return _check(root, use_git, strict)
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return ['datos mal formados: %s: %s (algún campo tiene un tipo equivocado)' % (type(e).__name__, e)], []


def _check(root, use_git=True, strict=False):
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
        evid, reg, pin = load(root, 'evidence.toml'), load(root, 'regression.toml'), load(root, 'policy.pin.toml')
    except DataError as e:
        return [str(e)], warns
    for fname, data, key in (('policy.toml', policy, 'actions'), ('tasks.toml', tasks, 'task'), ('decisions.toml', decs, 'decision'), ('evidence.toml', evid, 'evidence'), ('regression.toml', reg, 'suite')):
        v = data.get(key)
        if not (isinstance(v, list) and v and all(isinstance(x, dict) for x in v)): E('%s: «%s» debe ser una lista no vacía de tablas ([[%s]])' % (fname, key, key))
    if not (isinstance(pin.get('sha256'), str) and isinstance(pin.get('ratification'), str)): E('policy.pin.toml: faltan sha256 y ratification (cadenas)')
    if errs: return errs, warns
    roles = policy.get('roles', {}) if isinstance(policy.get('roles'), dict) else {}
    for r in ('director', 'jefe-tecnico', 'ingeniero'):
        if r not in roles: E('policy.toml: falta el rol %s' % r)
    tiers = policy.get('tiers', {}) if isinstance(policy.get('tiers'), dict) else {}
    if set(tiers) != set(TIER_ORDER): E('policy.toml: los niveles deben ser exactamente A, B, C, X')
    for t, v in tiers.items():
        if not isinstance(v, dict) or not v.get('name') or not v.get('color'): E('policy.toml: el nivel %s necesita name y color' % t)
        elif v.get('color') != COLOR.get(t, '').split(' ')[0]: E('policy.toml: el color del nivel %s debe ser %s' % (t, COLOR.get(t)))
    actions = {}
    for a in lst(policy.get('actions')):
        if not isinstance(a, dict): E('policy.toml: acción mal formada'); continue
        i = a.get('id')
        if not isinstance(i, str) or not re.fullmatch(r'[a-z0-9-]+', i): E('policy.toml: id de acción inválido %r' % i); continue
        if i in actions: E('policy.toml: acción duplicada %s' % i)
        actions[i] = a
        if a.get('tier') not in TIER_ORDER: E('policy.toml: acción %s con nivel inválido %r' % (i, a.get('tier')))
        if not a.get('summary'): E('policy.toml: acción %s sin resumen' % i)
        if a.get('tier') == 'C' and a.get('authorizer') != 'director': E('policy.toml: la acción C %s debe exigir al director' % i)
        if a.get('tier') == 'B' and a.get('reviewer') not in ('jefe-tecnico', 'director'): E('policy.toml: la acción B %s debe nombrar revisor' % i)
    # policy pin: a silent downgrade of an action tier changes the hash and fails until the pin (a reviewed, director-level change) is updated
    with open(os.path.join(gov, 'data', 'policy.toml'), 'rb') as f: phash = hashlib.sha256(f.read()).hexdigest()
    if pin.get('sha256') != phash: E('policy.toml cambió sin actualizar policy.pin.toml (acción policy-change, revisor: director): hash %s' % phash)
    # decisions
    dec = {}
    for d in lst(decs.get('decision')):
        if not isinstance(d, dict): E('decisión mal formada'); continue
        i = d.get('id', '?')
        if not isinstance(i, str) or not re.fullmatch(r'D-\d{4}', i): E('decisión con id inválido %r' % i)
        if i in dec: E('decisión duplicada %s' % i)
        dec[i] = d
        if d.get('status') not in DECISION_STATUS: E('%s: estado inválido %r' % (i, d.get('status')))
        if d.get('scope') not in DECISION_SCOPE: E('%s: ámbito inválido %r' % (i, d.get('scope')))
        for k in ('title', 'date', 'proposer', 'rationale', 'reversal'):
            if not d.get(k): E('%s: falta %s' % (i, k))
        if d.get('proposer') not in roles: E('%s: proponente desconocido %r' % (i, d.get('proposer')))
        auth = d.get('authorizes', [])
        if not isinstance(auth, list): E('%s: authorizes debe ser una lista' % i); auth = []
        for a in auth:
            if a not in actions: E('%s: authorizes cita una acción desconocida %r' % (i, a))
            elif actions[a].get('tier') != 'C': E('%s: authorizes solo puede citar acciones de nivel C (%s es %s)' % (i, a, actions[a].get('tier')))
        if auth and not (d.get('status') == 'APPROVED' and d.get('approved_by') == 'director' and d.get('scope') == 'operation'):
            E('%s: authorizes exige estado APPROVED, aprobador director y ámbito operation' % i)
        if d.get('valid_until'):
            try: datetime.date.fromisoformat(d['valid_until'])
            except ValueError: E('%s: valid_until no es una fecha ISO' % i)
        if d.get('status') == 'APPROVED':
            ab = d.get('approved_by')
            if ab not in roles: E('%s: APPROVED sin aprobador válido' % i)
            else:
                can = roles[ab].get('can_approve', [])
                if d.get('scope') not in can: E('%s: el rol %s no puede aprobar decisiones de ámbito %s' % (i, ab, d.get('scope')))
                if ab == d.get('proposer') == 'ingeniero': E('%s: el ingeniero no aprueba sus propias propuestas' % i)
            for k in ('approval_date', 'approval_ref'):
                if not d.get(k): E('%s: APPROVED sin %s' % (i, k))
        elif d.get('approved_by') and d.get('status') != 'SUPERSEDED': E('%s: tiene aprobador pero estado %s' % (i, d.get('status')))   # una decisión aprobada y luego sustituida conserva su aprobador (historia); ya no autoriza nada
    for i, d in dec.items():
        for s in lst(d.get('supersedes')):
            if s not in dec: E('%s supersede una decisión inexistente %s' % (i, s))
    rat = dec.get(pin.get('ratification', ''))
    if rat is None: E('policy.pin.toml: ratification cita una decisión inexistente')
    elif rat.get('status') != 'APPROVED': W('la política vigente (policy.toml) es una PROPUESTA: %s no está APPROVED' % pin.get('ratification'))
    # evidence: level / domain / device are DECLARED, never inferred or promoted
    ev = {}
    for e in lst(evid.get('evidence')):
        if not isinstance(e, dict): E('evidencia mal formada'); continue
        i = e.get('id', '?')
        if not isinstance(i, str) or not re.fullmatch(r'E-\d{4}', i): E('evidencia con id inválido %r' % i)
        if i in ev: E('evidencia duplicada %s' % i)
        ev[i] = e
        for k in ('title', 'kind', 'path', 'location', 'created', 'domain', 'level', 'device'):
            if not e.get(k): E('%s: falta %s' % (i, k))
        if e.get('immutable') and not re.fullmatch(r'[0-9a-f]{64}', e.get('sha256', '')): E('%s: evidencia inmutable sin SHA-256 válido' % i)
        if e.get('sha256') and not re.fullmatch(r'[0-9a-f]{64}', e['sha256']): E('%s: SHA-256 mal formado' % i)
        if 'size' in e and (not isinstance(e['size'], int) or e['size'] < 0): E('%s: size debe ser un entero' % i)
        lv, dm, dv = e.get('level'), e.get('domain'), e.get('device')
        if lv and lv not in LEVELS + ('n/a',): E('%s: nivel de evidencia inválido %r' % (i, lv))
        if dm and dm not in DOMAINS: E('%s: dominio inválido %r' % (i, dm))
        if dv and dv not in DEVICES: E('%s: dispositivo inválido %r' % (i, dv))
        if lv in ('L3', 'L4') and dv not in ('this-unit', 'upstream-device'): E('%s: una evidencia %s exige device this-unit o upstream-device' % (i, lv))
        if dm == 'host' and level_num(lv) > 2: E('%s: una prueba host no puede declarar %s (máximo L2)' % (i, lv))
        if dm == 'build' and lv != 'L1': E('%s: un resultado de compilación es L1, no %s' % (i, lv))
        if dm in ('gpu-device', 'ios-integration') and (lv not in ('L3', 'L4') or dv not in ('this-unit', 'upstream-device')): E('%s: el dominio %s exige nivel L3/L4 y device this-unit o upstream-device' % (i, dm))
        if dm == 'ios-integration' and lv != 'L4': E('%s: integración iOS es L4' % i)
        if dm == 'gpu-device' and lv != 'L3': E('%s: GPU física es L3' % i)
    # regression suites
    suites = {}
    for s in lst(reg.get('suite')):
        if not isinstance(s, dict): E('suite mal formada'); continue
        i = s.get('id', '?')
        if i in suites: E('suite duplicada %s' % i)
        suites[i] = s
        for k in ('title', 'baseline', 'domain', 'level'):
            if not s.get(k): E('suite %s: falta %s' % (i, k))
        for p in screen_command(root, s.get('command')): E('suite %s: %s' % (i, p))
        if s.get('cwd') and (os.path.isabs(s['cwd']) or '..' in s['cwd'].split('/')): E('suite %s: cwd fuera del repositorio' % i)
        dm, lv = s.get('domain'), s.get('level')
        if dm and dm not in DOMAINS: E('suite %s: dominio inválido %r' % (i, dm))
        if dm == 'host' and level_num(lv) > 2: E('suite %s: una suite host no puede declarar %s' % (i, lv))
        if dm == 'build' and lv != 'L1': E('suite %s: compilación es L1' % i)
        if dm in ('gpu-device', 'ios-integration'): E('suite %s: una suite automática del PC no puede declarar dominio %s (eso exige el teléfono)' % (i, dm))
        if s.get('known_failing') and not (isinstance(s.get('known_failure_count'), int) and s['known_failure_count'] > 0 and s.get('known_failure_pattern')):
            E('suite %s: known_failing exige known_failure_count (>0) y known_failure_pattern: la deuda se cuantifica, no se oculta' % i)
    # tasks
    tk = {}
    for t in lst(tasks.get('task')):
        if not isinstance(t, dict): E('tarea mal formada'); continue
        i = t.get('id', '?')
        if not isinstance(i, str) or not re.fullmatch(r'T-\d{4}', i): E('tarea con id inválido %r' % i)
        if i in tk: E('tarea duplicada %s' % i)
        tk[i] = t
        if t.get('status') not in TASK_STATUS: E('%s: estado inválido %r' % (i, t.get('status')))
        for k in ('title', 'owner', 'acceptance'):
            if not t.get(k): E('%s: falta %s' % (i, k))
        if not isinstance(t.get('priority'), int): E('%s: priority debe ser un entero' % i)
        if t.get('owner') and t['owner'] not in roles: E('%s: propietario desconocido %r' % (i, t.get('owner')))
        for k in ('depends_on', 'evidence', 'requires_decisions'):
            if k in t and not (isinstance(t[k], list) and all(isinstance(x, str) for x in t[k])): E('%s: %s debe ser una lista de cadenas' % (i, k))
        if not (isinstance(t.get('actions'), list) and t.get('actions')): E('%s: falta actions' % i)
        for a in lst(t.get('actions')):
            if a not in actions: E('%s: acción desconocida %r' % (i, a))
        for x in lst(t.get('evidence')):
            if x not in ev: E('%s: evidencia inexistente %s' % (i, x))
        for x in lst(t.get('requires_decisions')):
            if x not in dec: E('%s: requires_decisions cita una decisión inexistente %s' % (i, x))
            elif t.get('status') in ('in_progress', 'done') and dec[x].get('status') != 'APPROVED': E('%s: avanzada sin que la decisión %s esté APPROVED' % (i, x))
        if t.get('status') == 'blocked' and not t.get('blocked_on'): E('%s: bloqueada sin blocked_on' % i)
        if t.get('status') == 'ready' and t.get('blocked_on'): E('%s: está ready pero declara blocked_on: o está bloqueada o no lo está' % i)
        tier = tier_of_actions(policy, lst(t.get('actions')))
        if tier == 'X' and t.get('status') != 'cancelled' and all(a in actions for a in lst(t.get('actions'))): E('%s: contiene una acción prohibida (X)' % i)
        if t.get('status') in ('in_progress', 'in_review', 'done'):
            cacts = [a for a in lst(t.get('actions')) if actions.get(a, {}).get('tier') == 'C']
            if cacts:
                ref = t.get('authorization_ref')
                if ref not in dec: E('%s: acción C en curso/hecha sin authorization_ref a una decisión' % i)
                else:
                    if not (dec[ref].get('status') == 'APPROVED' and dec[ref].get('approved_by') == 'director'): E('%s: authorization_ref %s no es una decisión APPROVED del director' % (i, ref))
                    else:
                        for a in cacts:
                            ok, why = decision_ok_for(dec, ref, a, 'director')
                            if not ok: E('%s: %s' % (i, why))
        if t.get('status') == 'done':
            for a in [a for a in lst(t.get('actions')) if actions.get(a, {}).get('tier') == 'B']:
                rv = actions[a].get('reviewer'); ref = t.get('review_ref'); d = dec.get(ref)
                okroles = ('jefe-tecnico', 'director') if rv == 'jefe-tecnico' else ('director',)
                if not (d and d.get('status') == 'APPROVED' and d.get('approved_by') in okroles): E('%s: la acción amarilla %s exige review_ref a una decisión APPROVED de %s antes de pasar a done' % (i, a, ' o '.join(okroles)))
        me = t.get('min_evidence')
        if me is not None and t.get('status') in ('in_review', 'done'):
            ok = any(level_num(ev.get(x, {}).get('level')) >= level_num(me.get('level', 'L9')) and ev.get(x, {}).get('device') == me.get('device') for x in lst(t.get('evidence')))
            if not ok: E('%s: exige evidencia %s en %s y ninguna de sus evidencias lo cumple (los niveles no se elevan solos)' % (i, me.get('level'), me.get('device')))
    for i, t in tk.items():
        for dep in lst(t.get('depends_on')):
            if dep not in tk: E('%s: depende de una tarea inexistente %s' % (i, dep))
            elif tk[dep].get('status') != 'done':
                if t.get('status') == 'done': E('%s: done con dependencia %s sin terminar' % (i, dep))
                elif t.get('status') == 'in_progress': E('%s: en curso pero su dependencia %s no está done' % (i, dep))   # in_review may wait on dependencies
    state = {}
    def dfs(n, path):
        state[n] = 1
        for m in lst(tk.get(n, {}).get('depends_on')):
            if m not in tk: continue
            if state.get(m) == 1: E('ciclo de dependencias: %s' % ' -> '.join(path + [n, m]))
            elif m not in state: dfs(m, path + [n])
        state[n] = 2
    for n in tk:
        if n not in state: dfs(n, [])
    active = [i for i, t in tk.items() if t.get('status') == 'in_progress']
    if len(active) > 1: E('más de una tarea en curso: %s' % ', '.join(active))
    # generated views must be current (computed in memory: nothing is written)
    if not errs:
        try:
            for fn, want in render_all(root).items():
                p = os.path.join(gov, fn)
                have = open(p, encoding='utf-8').read() if os.path.isfile(p) else ''
                if have != want: E('governance/%s está desactualizado: ejecuta `python3 tools/governance.py render`' % fn)
        except (KeyError, TypeError, ValueError) as e: E('no se pueden generar las vistas: %s: %s' % (type(e).__name__, e))
    # links in the hand-written documents and in checkpoints
    docs = [os.path.join(gov, d) for d in REQUIRED_DOCS]
    cdir = os.path.join(gov, 'checkpoints')
    if os.path.isdir(cdir): docs += [os.path.join(cdir, f) for f in sorted(os.listdir(cdir)) if f.endswith('.md')]
    for p in docs:
        base = os.path.dirname(p)
        for m in re.finditer(r'\]\(([^)#\s]+)(?:#[^)]*)?\)', open(p, encoding='utf-8').read()):
            tgt = m.group(1)
            if re.match(r'^[a-z]+:', tgt): continue
            if not os.path.exists(os.path.normpath(os.path.join(base, tgt))): E('%s: enlace roto -> %s' % (os.path.relpath(p, root), tgt))
    ag = os.path.join(root, 'AGENTS.md')
    if not os.path.isfile(ag) or 'governance/README.md' not in open(ag, encoding='utf-8').read(): E('AGENTS.md no apunta a governance/README.md')
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
                if rc == 0 and n != '0': (E if strict else W)('STATE.md describe el commit %s; HEAD lleva %s commit(s) más: revisar si el estado sigue vigente' % (m.group(1)[:8], n))
    return errs, warns


# --------------------------------------------------------------------------------------------------------------------------------- render
def esc(s): return str(s).replace('|', '\\|').replace('\n', ' ')


def render_all(root):
    policy, tasks, decs = load(root, 'policy.toml'), load(root, 'tasks.toml'), load(root, 'decisions.toml')
    evid = load(root, 'evidence.toml')
    tk = sorted([t for t in lst(tasks.get('task')) if isinstance(t, dict)], key=lambda t: (t['priority'] if isinstance(t.get('priority'), int) else 99, str(t.get('id', ''))))
    out = {}
    L = [GENERATED, '# Cola de tareas\n', 'Ordenada por prioridad (1 = la más urgente). "Nivel" = el más alto de sus acciones (`policy.toml`): **A** verde (autónomo), **B** amarillo (revisión antes de consolidar), **C** rojo (autorización explícita del Director), **X** rojo/prohibido. Una acción desconocida cuenta como X.\n',
         '| ID | Estado | Prio | Propietario | Título | Depende de | Nivel | Bloqueo |', '|---|---|---|---|---|---|---|---|']
    for t in tk:
        tr = tier_of_actions(policy, lst(t.get('actions')))
        L.append('| %s | %s | %s | %s | %s | %s | %s %s | %s |' % (t['id'], t['status'], t.get('priority', ''), t.get('owner', ''), esc(t['title']), ', '.join(lst(t.get('depends_on'))) or '—', tr, COLOR[tr].split(' ')[0], esc(t.get('blocked_on', '')) or '—'))
    L += ['', '## Criterios de aceptación\n']
    for t in tk: L.append('- **%s** %s: %s' % (t['id'], esc(t['title']), esc(t.get('acceptance', ''))))
    out['TASKS.md'] = '\n'.join(L) + '\n'
    A = [GENERATED, '# Tarea activa\n']
    nxt, mode = next_task(policy, tasks, decs)
    if nxt and mode == 'resume':
        t = nxt
        A += ['**%s — %s**\n' % (t['id'], t['title']), '- Estado: `in_progress`  - Nivel: %s' % tier_of_actions(policy, lst(t.get('actions'))), '- Acciones: %s' % ', '.join(lst(t.get('actions'))),
              '- Depende de: %s' % (', '.join(lst(t.get('depends_on'))) or '—'), '- Aceptación: %s' % t.get('acceptance', ''), '- Notas de reanudación: %s' % (t.get('resume', '—') or '—')]
    else:
        A += ['**No hay ninguna tarea en curso.**\n', 'Tareas pendientes de revisión: %s' % (', '.join('%s (%s)' % (t['id'], t['title']) for t in tk if t['status'] == 'in_review') or '—'), '',
              'Siguiente tarea que se puede empezar sin pedir autorización: %s' % ('**%s — %s**%s' % (nxt['id'], nxt['title'], ' (amarilla: solo en local, sin consolidar)' if tier_of_actions(policy, lst(nxt.get('actions'))) == 'B' else '') if nxt else '— (todo bloqueado: ver `TASKS.md`)')]
    A += ['', '## Cómo reanudar', '1. Lee `README.md` y `HANDOFF.md`; ejecuta `python3 tools/governance.py check` y `status`.', '2. Si hay tarea en curso, sigue su campo `resume` y el último fichero de `checkpoints/`.',
          '3. Si no la hay, toma la que indique `python3 tools/governance.py next`, márcala `in_progress` en `data/tasks.toml`, ejecuta `render` y anota el primer checkpoint.']
    out['ACTIVE_TASK.md'] = '\n'.join(A) + '\n'
    D = [GENERATED, '# Registro de decisiones\n', 'Estados: `PROPOSED` (propuesta, **sin efecto**), `APPROVED` (aprobada por quien tiene autoridad para ese ámbito, con referencia), `REJECTED`, `SUPERSEDED`. Una propuesta del ingeniero **no es una decisión aprobada**. Una decisión autoriza una acción roja solo si la lista en `authorizes` (y está vigente).\n',
         '| ID | Estado | Ámbito | Fecha | Título | Propone | Aprueba | Autoriza | Referencia |', '|---|---|---|---|---|---|---|---|---|']
    ds = sorted([d for d in lst(decs.get('decision')) if isinstance(d, dict)], key=lambda d: str(d.get('id', '')))
    for d in ds:
        D.append('| %s | %s | %s | %s | %s | %s | %s | %s | %s |' % (d['id'], d['status'], d['scope'], d['date'], esc(d['title']), d['proposer'], d.get('approved_by', '—'), ', '.join(lst(d.get('authorizes'))) or '—', esc(d.get('approval_ref', '—'))))
    D.append('')
    for d in ds:
        D += ['## %s — %s' % (d['id'], d['title']), '- **Estado:** %s%s' % (d['status'], ' (%s, %s)' % (d.get('approved_by'), d.get('approval_date')) if d['status'] == 'APPROVED' else ''),
              '- **Razón:** %s' % d['rationale'], '- **Consecuencias:** %s' % d.get('consequences', '—'), '- **Cómo se revierte:** %s' % d['reversal']]
        if d.get('supersedes'): D.append('- **Sustituye a:** %s' % ', '.join(d['supersedes']))
        D.append('')
    out['DECISIONS.md'] = '\n'.join(D) + '\n'
    V = [GENERATED, '# Índice de evidencias\n', 'Evidencia = artefacto cuyo hash respalda una afirmación. Las **inmutables** no se editan, mueven ni borran; se añaden versiones nuevas con otro nombre. **Dominio y nivel son declaraciones, nunca se infieren ni se elevan automáticamente:** una prueba del PC (host) no pasa a ser de hardware. Verificar: `python3 tools/governance.py evidence [--all] [--strict]`.\n',
         '| ID | Dominio | Nivel | Dispositivo | Tipo | Título | Ubicación | Ruta | SHA-256 | Inmutable |', '|---|---|---|---|---|---|---|---|---|---|']
    for e in sorted([e for e in lst(evid.get('evidence')) if isinstance(e, dict)], key=lambda e: str(e.get('id', ''))):
        V.append('| %s | %s | %s | %s | %s | %s | %s | `%s` | `%s` | %s |' % (e['id'], e.get('domain', ''), e.get('level', ''), e.get('device', ''), e['kind'], esc(e['title']), e['location'], e['path'],
                                                                            (e.get('sha256') or '—')[:16] + ('…' if e.get('sha256') else ''), 'sí' if e.get('immutable') else 'no'))
    out['EVIDENCE.md'] = '\n'.join(V) + '\n'
    return out


def next_task(policy, tasks, decs=None):
    """(task, mode). Resumes the task in progress; otherwise the best READY task that is owned by the engineer, not blocked, with every dependency done and
    every required decision APPROVED, whose actions are all known and green or yellow. Red/forbidden/unknown-action tasks are never selected."""
    tk = {t.get('id'): t for t in lst(tasks.get('task')) if isinstance(t, dict)}
    dec = {d.get('id'): d for d in lst((decs or {}).get('decision'))} if decs is not None else None
    act = [t for t in tk.values() if t.get('status') == 'in_progress']
    if act: return sorted(act, key=lambda t: (t.get('priority', 99) if isinstance(t.get('priority'), int) else 99, t.get('id')))[0], 'resume'
    acts = {a.get('id') for a in lst(policy.get('actions'))}
    cands = []
    for t in tk.values():
        if t.get('status') != 'ready' or t.get('owner') != 'ingeniero' or t.get('blocked_on'): continue
        if not isinstance(t.get('priority'), int): continue
        if any(tk.get(d, {}).get('status') != 'done' for d in lst(t.get('depends_on'))): continue
        if dec is not None and any(dec.get(x, {}).get('status') != 'APPROVED' for x in lst(t.get('requires_decisions'))): continue
        if not lst(t.get('actions')) or any(a not in acts for a in lst(t.get('actions'))): continue
        if tier_of_actions(policy, t['actions']) in ('C', 'X'): continue
        cands.append(t)
    cands.sort(key=lambda t: (t['priority'], t['id']))
    return (cands[0], 'start') if cands else (None, None)


# ------------------------------------------------------------------------------------------------------------------------------ commands
def write_generated(root, fn, text):
    """Atomic write of ONE generated view. Refuses any other name and any existing file that is not a generated view."""
    if fn not in GENERATED_VIEWS: raise DataError('render solo puede escribir %s, no %s' % (', '.join(GENERATED_VIEWS), fn))
    d = os.path.join(root, 'governance'); p = os.path.join(d, fn)
    if os.path.lexists(p):
        if os.path.islink(p): raise DataError('governance/%s es un enlace simbólico: no se escribe' % fn)
        if not open(p, encoding='utf-8').read().startswith(GENERATED): raise DataError('governance/%s existe y NO es un fichero generado: no se sobrescribe' % fn)
    fd, tmp = tempfile.mkstemp(prefix='.render-', suffix='.tmp', dir=d)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f: f.write(text)
        os.replace(tmp, p)
    except BaseException:
        if os.path.exists(tmp): os.unlink(tmp)
        raise


def cmd_render(root, check_only):
    bad = 0
    views = render_all(root)                       # everything is computed BEFORE the first write: a data error leaves the files untouched
    for fn, text in views.items():
        p = os.path.join(root, 'governance', fn)
        have = open(p, encoding='utf-8').read() if os.path.isfile(p) else None
        if have == text: continue
        if check_only: print('DESACTUALIZADO governance/%s' % fn); bad += 1
        else: write_generated(root, fn, text); print('escrito governance/%s' % fn)
    return 1 if bad else 0


def cmd_can(root, action):
    policy = load(root, 'policy.toml'); a = {x.get('id'): x for x in lst(policy.get('actions'))}.get(action)
    if not a or a.get('tier') not in TIER_ORDER:
        print('acción desconocida: %s (se trata como PROHIBIDA, no como libre)\nacciones: %s' % (action, ', '.join(sorted(x.get('id', '?') for x in lst(policy.get('actions')))))); return 2
    t = a['tier']; name = policy['tiers'][t]['name']
    print('%s: nivel %s %s (%s)\n  %s' % (action, t, COLOR[t].upper(), name, a.get('summary', '')))
    if a.get('requires'): print('  condiciones: ' + '; '.join(a['requires']))
    if t == 'B': print('  revisor antes de consolidar: %s' % a.get('reviewer'))
    if t == 'C': print('  autoriza: %s, de forma explícita, acotada y registrada en decisions.toml (campo authorizes)' % a.get('authorizer'))
    if t == 'X': print('  prohibida por regla del proyecto; solo el Director puede cambiarla modificando AGENTS.md y policy.toml')
    print('  NOTA: esto es una consulta; no es una autorización.')
    return EXIT_BY_TIER[t]


def cmd_gate(root, action, task_id, consolidate):
    policy, tasks, decs = load(root, 'policy.toml'), load(root, 'tasks.toml'), load(root, 'decisions.toml')
    a = {x.get('id'): x for x in lst(policy.get('actions'))}.get(action)
    if not a or a.get('tier') not in TIER_ORDER: print('DENEGADA %s: acción desconocida (se trata como prohibida)' % action); return 2
    dec = {d.get('id'): d for d in lst(decs.get('decision'))}; tk = {t.get('id'): t for t in lst(tasks.get('task'))}
    t = a['tier']; task = tk.get(task_id) if task_id else None
    if task_id and task is None: print('DENEGADA %s: la tarea %s no existe' % (action, task_id)); return 20 if t == 'C' else 2
    if task is not None and action not in lst(task.get('actions')): print('DENEGADA %s: la tarea %s no declara esa acción' % (action, task_id)); return 20 if t in ('C', 'X') else 2
    if t == 'X': print('PROHIBIDA %s (nivel X): ninguna autorización registrada la habilita' % action); return 30
    if t == 'A': print('PERMITIDA %s (verde): autónoma. Esta salida no ejecuta nada.' % action); return 0
    if t == 'B':
        if not consolidate: print('PERMITIDA SOLO EN LOCAL %s (amarillo): se puede implementar y confirmar en local; NO consolidar sin revisión de %s' % (action, a.get('reviewer'))); return 10
        ref = (task or {}).get('review_ref'); d = dec.get(ref)
        okroles = ('jefe-tecnico', 'director') if a.get('reviewer') == 'jefe-tecnico' else ('director',)
        if d and d.get('status') == 'APPROVED' and d.get('approved_by') in okroles: print('CONSOLIDACIÓN PERMITIDA %s: revisión registrada en %s (%s)' % (action, ref, d.get('approved_by'))); return 11
        print('CONSOLIDACIÓN DENEGADA %s (amarillo): falta review_ref a una decisión APPROVED de %s' % (action, ' o '.join(okroles))); return 12
    # red
    if task is None: print('DENEGADA %s (rojo): sin --task no hay autorización registrada que consultar' % action); return 20
    ref = task.get('authorization_ref')
    if not ref: print('DENEGADA %s (rojo): la tarea %s no tiene authorization_ref' % (action, task_id)); return 20
    ok, why = decision_ok_for(dec, ref, action, 'director')
    print(('AUTORIZACIÓN REGISTRADA %s: %s. Esta salida NO ejecuta nada ni sustituye la confirmación del Director en el momento.' if ok else 'DENEGADA %s (rojo): %s') % (action, why)); return 0 if ok else 20


def cmd_next(root):
    policy, tasks, decs = load(root, 'policy.toml'), load(root, 'tasks.toml'), load(root, 'decisions.toml')
    n, mode = next_task(policy, tasks, decs)
    if not n: print('ninguna tarea autónoma disponible: todo está bloqueado, depende de decisiones sin aprobar o necesita autorización (ver governance/TASKS.md)'); return 1
    tr = tier_of_actions(policy, n['actions'])
    print('%s %s  %s\n  nivel %s (%s)%s\n  aceptación: %s' % ('REANUDAR' if mode == 'resume' else 'EMPEZAR', n['id'], n['title'], tr, COLOR[tr].split(' ')[0],
                                                           ' — solo en local, NO consolidar sin revisión' if tr == 'B' else '', n['acceptance']))
    print('  NOTA: seleccionar una tarea no es una autorización de ninguna acción roja.'); return 0


def cmd_status(root, use_git=True):
    policy, tasks, decs = load(root, 'policy.toml'), load(root, 'tasks.toml'), load(root, 'decisions.toml')
    print('raíz: %s' % root)
    if use_git:
        _, br = git(root, 'branch', '--show-current'); _, head = git(root, 'log', '--oneline', '-1'); _, dirty = git(root, 'status', '--porcelain')
        print('rama: %s\nHEAD: %s\nsin confirmar: %d fichero(s)' % (br, head, len([l for l in dirty.splitlines() if l])))
        _, wt = git(root, 'worktree', 'list')
        if wt.count('\n'): print('worktrees:\n  ' + wt.replace('\n', '\n  '))
    tk = lst(tasks.get('task')); by = {}
    for t in tk: by[t['status']] = by.get(t['status'], 0) + 1
    print('tareas: ' + ', '.join('%s=%d' % kv for kv in sorted(by.items())))
    act = [t for t in tk if t['status'] == 'in_progress']
    print('en curso: %s' % (', '.join('%s %s' % (t['id'], t['title']) for t in act) or 'ninguna'))
    n, mode = next_task(policy, tasks, decs); print('siguiente: %s' % (('%s %s (%s)' % (n['id'], n['title'], mode)) if n else 'ninguna'))
    pend = [d for d in lst(decs.get('decision')) if d['status'] == 'PROPOSED']
    print('decisiones PROPOSED sin aprobar: %d (%s)' % (len(pend), ', '.join(d['id'] for d in pend)))
    print('bloqueadas: ' + '; '.join('%s [%s]' % (t['id'], t['blocked_on']) for t in tk if t['status'] == 'blocked'))
    print('NOTA: este resumen no autoriza ninguna acción.'); return 0


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 22), b''): h.update(b)
    return h.hexdigest()


def evidence_path(root, e):
    p = e['path']
    return os.path.expanduser(p) if p.startswith('~') else (p if os.path.isabs(p) else os.path.join(root, p))


def cmd_evidence(root, all_, strict=False):
    """Only state OK means "this file is the one recorded". Everything else is reported with its own state; nothing is promoted."""
    evid = load(root, 'evidence.toml'); counts = {}
    def note(state, e, msg): counts[state] = counts.get(state, 0) + 1; print('%-12s %s [%s %s %s] %s' % (state, e['id'], e.get('domain', '?'), e.get('level', '?'), e.get('device', '?'), msg))
    for e in sorted(lst(evid.get('evidence')), key=lambda e: e['id']):
        p = evidence_path(root, e); h = e.get('sha256')
        if not h: note('SIN-HASH', e, '%s: un registro sin hash NO prueba nada' % e['title']); continue
        if os.path.islink(p): note('SYMLINK', e, '%s es un enlace simbólico: no se acepta como evidencia' % e['path']); continue
        if not os.path.isfile(p): note('AUSENTE', e, 'no existe en esta máquina: %s' % e['path']); continue
        sz = os.path.getsize(p)
        if isinstance(e.get('size'), int) and sz != e['size']: note('TAMAÑO', e, '%s mide %d y se registró con %d' % (e['path'], sz, e['size'])); continue
        if sz > (1 << 30) and not all_: note('GRANDE', e, 'mayor de 1 GiB: no verificada (usa --all)'); continue
        if sha256_file(p) == h: note('OK', e, e['title'])
        else: note('MODIFICADA' if e.get('immutable') else 'DESACTUALIZADA', e, '%s: el hash NO coincide con el registrado' % e['path'])
    bad = counts.get('MODIFICADA', 0) + counts.get('TAMAÑO', 0) + counts.get('SYMLINK', 0) + counts.get('DESACTUALIZADA', 0)
    unverified = sum(counts.get(k, 0) for k in ('AUSENTE', 'GRANDE', 'SIN-HASH'))
    print('RESUMEN evidencias: %s' % ', '.join('%d %s' % (v, k) for k, v in sorted(counts.items())))
    print('Solo las OK están verificadas en esta máquina; %d no se pudieron verificar. Ningún resultado eleva el nivel declarado de una evidencia.' % unverified)
    return 1 if bad or (strict and unverified) else 0


def cmd_regress(root, suite, list_only, strict=False, use_git=True):
    reg = load(root, 'regression.toml'); rows = []; failed = 0
    suites = [s for s in lst(reg.get('suite')) if isinstance(s, dict)]
    if suite and not any(s.get('id') == suite for s in suites): print('suite desconocida: %s' % suite); return 2
    for s in suites:
        if suite and s.get('id') != suite: continue
        if list_only: print('%-22s %-9s [%s %s] %s\n    baseline: %s' % (s['id'], s.get('cost', ''), s.get('domain', ''), s.get('level', ''), s['title'], s['baseline'])); continue
        prob = screen_command(root, s.get('command'))
        if prob: rows.append((s['id'], 'FALLA', 'RECHAZADA por la pantalla de seguridad: ' + '; '.join(prob), 0, s)); failed += 1; continue
        miss = [r for r in lst(s.get('requires')) if not os.path.exists(os.path.expanduser(r) if r.startswith('~') else os.path.join(root, r))]
        if miss: rows.append((s['id'], 'SKIP', 'falta: ' + ', '.join(miss), 0, s)); continue
        before = tree_fingerprint(root) if use_git else None
        t0 = time.time(); cwd = os.path.join(root, s['cwd']) if s.get('cwd') else root
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', GOVERNANCE_REGRESS='1')
        try:
            r = subprocess.run([os.path.expanduser(x) if x.startswith('~') else x for x in s['command']], cwd=cwd, capture_output=True, text=True, timeout=s.get('timeout', 900), env=env)
            out, rc = r.stdout + r.stderr, r.returncode
        except subprocess.TimeoutExpired: out, rc = 'tiempo agotado (%ss)' % s.get('timeout', 900), -9
        except OSError as e: out, rc = 'no se pudo ejecutar: %s' % e, -1
        tail = out.strip().splitlines()[-1:] or ['']
        known = bool(s.get('known_failing'))
        st = ('PASS' if rc == 0 else 'FALLA') if not known else ('XPASS' if rc == 0 else 'XFAIL')
        msg = tail[0][:110]
        if known and rc != 0:
            clean = re.sub(r'\x1b\[[0-9;]*m', '', out); n = len(re.findall(s['known_failure_pattern'], clean))
            msg = 'deuda conocida: %d fallo(s) de patrón %r (línea base %s)' % (n, s['known_failure_pattern'], s['known_failure_count'])
            if n > s['known_failure_count']: st = 'FALLA'; msg += ' — HAN AUMENTADO'
        if before is not None and tree_fingerprint(root) != before: st = 'FALLA'; msg = 'LA SUITE MODIFICÓ EL ÁRBOL GIT (ficheros o HEAD); ' + msg
        rows.append((s['id'], st, msg, time.time() - t0, s)); failed += (st == 'FALLA')
    if list_only: return 0
    for i, st, msg, dt, s in rows: print('%-5s %-22s %5.1fs [%s %s] %s' % (st, i, dt, s.get('domain', '?'), s.get('level', '?'), msg))
    n = lambda k: sum(r[1] == k for r in rows)
    print('RESUMEN regresión: %d PASS, %d FALLA, %d SKIP, %d XFAIL (deuda conocida, cuantificada), %d XPASS (revisar known_failing)' % (n('PASS'), failed, n('SKIP'), n('XFAIL'), n('XPASS')))
    by = {}
    for r in rows:
        if r[1] == 'PASS': by.setdefault('%s %s' % (r[4].get('domain'), r[4].get('level')), []).append(r[0])
    for k, v in sorted(by.items()): print('  superadas en %s: %s' % (k, ', '.join(v)))
    print('  Una suite superada solo respalda su dominio y nivel declarados; ninguna eleva el nivel de otra.')
    return 1 if failed or (strict and n('SKIP')) else 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))); ap.add_argument('--no-git', action='store_true')
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('check'); p.add_argument('--strict', action='store_true')
    p = sub.add_parser('render'); p.add_argument('--check', action='store_true')
    p = sub.add_parser('can'); p.add_argument('action')
    p = sub.add_parser('gate'); p.add_argument('action'); p.add_argument('--task'); p.add_argument('--consolidate', action='store_true')
    sub.add_parser('next'); sub.add_parser('status')
    p = sub.add_parser('evidence'); p.add_argument('--all', action='store_true'); p.add_argument('--strict', action='store_true')
    p = sub.add_parser('regress'); p.add_argument('--suite'); p.add_argument('--list', action='store_true'); p.add_argument('--strict', action='store_true')
    a = ap.parse_args(argv)
    try:
        if a.cmd == 'check':
            errs, warns = check(a.root, not a.no_git, a.strict)
            for w in warns: print('AVISO  ' + w)
            for e in errs: print('ERROR  ' + e)
            print('RESUMEN gobierno: %d error(es), %d aviso(s)' % (len(errs), len(warns))); return 1 if errs else 0
        if a.cmd == 'render': return cmd_render(a.root, a.check)
        if a.cmd == 'can': return cmd_can(a.root, a.action)
        if a.cmd == 'gate': return cmd_gate(a.root, a.action, a.task, a.consolidate)
        if a.cmd == 'next': return cmd_next(a.root)
        if a.cmd == 'status': return cmd_status(a.root, not a.no_git)
        if a.cmd == 'evidence': return cmd_evidence(a.root, a.all, a.strict)
        if a.cmd == 'regress': return cmd_regress(a.root, a.suite, a.list, a.strict, not a.no_git)
    except DataError as e:
        print('ERROR de datos: %s' % e, file=sys.stderr); return 3
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        print('ERROR de datos mal formados (%s: %s). Ejecuta `check` para ver el detalle; no se ha escrito nada.' % (type(e).__name__, e), file=sys.stderr); return 3


if __name__ == '__main__':
    sys.exit(main())
