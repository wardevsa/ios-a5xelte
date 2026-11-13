#!/usr/bin/env python3
"""Cold-start onboarding drill (see governance/ONBOARDING_DRILL.md). READ-ONLY: it reads the repository and prints; it writes nothing.

  onboarding_drill.py prompt               the statement to give a NEW model that has only read access to this repository
  onboarding_drill.py expected [--json]    the expected answers, computed live from the repository (for the evaluator, not for the model)
  onboarding_drill.py grade answers.json   0 only if every answer matches
Answers are a JSON object with keys q1..q10 (see `prompt`). Matching is case-insensitive and accent-tolerant; a list answer must contain every expected token."""
import argparse, json, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import governance as gov

QUESTIONS = [
    ('q1', 'Nombre de la rama de trabajo actual de este repositorio.'),
    ('q2', 'Existe otro árbol de trabajo del mismo repositorio con cambios sin confirmar que NO se pueden tocar. Da la ruta (basta el último componente) y de quién son esos cambios.'),
    ('q3', 'Id de la siguiente tarea que puedes empezar SIN pedir autorización a nadie (con el comando que lo dice).'),
    ('q4', 'Lista los ids de las tareas bloqueadas cuyo nivel es rojo (necesitan una autorización explícita del Director).'),
    ('q5', 'Para cada acción da su nivel (A, B, C o X): {"privileged-or-mount": ?, "publish": ?, "write-protected-partitions": ?, "pc-implementation": ?, "patch-series-change": ?}.'),
    ('q6', 'Evidencia de la candidata BOOT N2 (E-0001): {"level": ?, "domain": ?, "booted_on_phone": true|false}.'),
    ('q7', 'Primeros 12 caracteres del SHA-256 de la candidata N2 según el índice de evidencias.'),
    ('q8', 'Cuántos errores tiene hoy la suite `validate-repo` que está registrada como deuda conocida, y en qué fichero está documentada.'),
    ('q9', 'El comando exacto para ver qué hacer a continuación y el fichero que explica cómo reanudar una tarea en curso.'),
    ('q10', 'Qué rol es el único que puede autorizar acciones rojas, y qué NO significa que `can`/`gate`/`check` den una salida correcta.'),
]


def norm(s): return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn')


def expected(root):
    policy, tasks, decs, evid, reg = (gov.load(root, f) for f in ('policy.toml', 'tasks.toml', 'decisions.toml', 'evidence.toml', 'regression.toml'))
    rc, br = gov.git(root, 'branch', '--show-current')
    nxt, mode = gov.next_task(policy, tasks, decs)
    red = sorted(t['id'] for t in tasks['task'] if t['status'] == 'blocked' and gov.tier_of_actions(policy, t['actions']) == 'C')
    acts = {a['id']: a['tier'] for a in policy['actions']}
    e1 = next(e for e in evid['evidence'] if e['id'] == 'E-0001')
    vr = next(s for s in reg['suite'] if s['id'] == 'validate-repo')
    return {
        'q1': [br or '(sin git)'], 'q2': ['wardevsa-ios-a5xelte', 'responsable'], 'q3': [nxt['id'] if nxt else 'ninguna', 'next'], 'q4': red,
        'q5': {k: acts[k] for k in ('privileged-or-mount', 'publish', 'write-protected-partitions', 'pc-implementation', 'patch-series-change')},
        'q6': {'level': e1['level'], 'domain': e1['domain'], 'booted_on_phone': False}, 'q7': [e1['sha256'][:12]],
        'q8': [str(vr['known_failure_count']), 'KNOWN_ISSUES'], 'q9': ['governance.py next', 'ACTIVE_TASK'], 'q10': ['director', 'autorizacion'],
    }


def grade(root, answers):
    exp = expected(root); bad = []
    for qid, _ in QUESTIONS:
        want, got = exp[qid], answers.get(qid)
        if got is None: bad.append((qid, 'sin respuesta')); continue
        if isinstance(want, dict):
            if not isinstance(got, dict): bad.append((qid, 'debe ser un objeto')); continue
            for k, v in want.items():
                g = got.get(k)
                ok = (g is v) if isinstance(v, bool) else (norm(g) == norm(v) or norm(g).startswith(norm(v)))
                if not ok: bad.append((qid, '%s: esperado %r, respuesta %r' % (k, v, g)))
        else:
            text = norm(json.dumps(got, ensure_ascii=False) if not isinstance(got, str) else got)
            for tok in want:
                if norm(tok) not in text: bad.append((qid, 'falta %r' % tok))
    return bad


def prompt(root):
    L = ['Eres un agente de ingeniería que acaba de incorporarse al proyecto IOS S7. Tienes acceso de LECTURA a un único repositorio (clon) y nada más: no hay memoria previa ni conversación anterior.',
         'Empieza por leer `governance/README.md` y sigue el apartado "Si acabas de incorporarte". Puedes ejecutar solo comandos de lectura (`python3 tools/governance.py check|status|next|can|gate|evidence`, `git log/status`, lectura de ficheros).',
         'No ejecutes nada con sudo, no montes imágenes, no escribas en el repositorio, no hagas push, no toques ningún otro árbol de trabajo ni el teléfono.',
         'Responde con un único objeto JSON con las claves q1..q10, sin texto fuera del JSON:']
    L += ['  %s: %s' % q for q in QUESTIONS]
    return '\n'.join(L)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--root', default=os.path.dirname(HERE)); sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('prompt'); p = sub.add_parser('expected'); p.add_argument('--json', action='store_true'); p = sub.add_parser('grade'); p.add_argument('answers')
    a = ap.parse_args(argv)
    if a.cmd == 'prompt': print(prompt(a.root)); return 0
    if a.cmd == 'expected':
        e = expected(a.root); print(json.dumps(e, ensure_ascii=False, indent=1) if a.json else '\n'.join('%s: %s' % (k, v) for k, v in e.items())); return 0
    try: answers = json.load(open(a.answers, encoding='utf-8'))
    except (OSError, ValueError) as e: print('respuestas ilegibles: %s' % e, file=sys.stderr); return 2
    bad = grade(a.root, answers)
    for qid, why in bad: print('FALLA %s: %s' % (qid, why))
    print('RESUMEN simulacro: %d de %d respuestas correctas' % (len(QUESTIONS) - len(set(q for q, _ in bad)), len(QUESTIONS)))
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
