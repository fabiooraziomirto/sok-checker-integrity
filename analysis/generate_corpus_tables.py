#!/usr/bin/env python3
"""Generate corpus table bodies from the canonical record, optionally update clean TeX."""
import argparse
import csv
import re
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).parent.parent
MODE = {'formally established': 'FE', 'statistically bounded': 'SB', 'empirically evaluated': 'EE'}
STATUS = {'evaluated': 'Ev', 'proposed_not_evaluated': 'Pd', 'not_addressed': 'Na', 'not_applicable': '---', 'unknown': 'Uk'}
OUTCOME = {'established': 'est.', 'open_declared': 'open (decl.)', 'open': 'open', 'n_a': 'n/a'}

def escape(text):
    return ''.join({'&': r'\&', '%': r'\%', '_': r'\_', '#': r'\#', '{': r'\{', '}': r'\}', '$': r'\$', '\\': r'\textbackslash{}'}.get(c, c) for c in text)

def table_bodies():
    with (ROOT / 'corpus/final_coding.csv').open(newline='') as f:
        rows = list(csv.DictReader(f))
    per_source = '\n'.join(r'\cite{' + r['citekey'] + '} & ' + r['paradigm'] + ' & ' + MODE[r['evidence_strength']] + ' & ' + ' & '.join(STATUS[r[a + '_evidence_status']] for a in ('AC1', 'AC2', 'AC3', 'bypass')) + r' \\' for r in rows)
    transfer = '\n'.join(r'\cite{' + r['citekey'] + '} & ' + MODE[r['evidence_strength']] + r' & \textsc{' + OUTCOME[r['transfer_outcome']] + '} & ' + escape(r['transfer_locator']) + r' \\' for r in rows)
    counts = Counter((r['evidence_strength'], r['transfer_outcome']) for r in rows)
    cross = '\n'.join(mode.capitalize() + ' & ' + ' & '.join(str(counts[mode, outcome]) for outcome in OUTCOME) + r' \\' for mode in MODE)
    cross += '\n'+r'\midrule'+'\nTotal & ' + ' & '.join(str(sum(counts[m, o] for m in MODE)) for o in OUTCOME) + r' \\'
    with (ROOT / 'corpus/screening_inventory.csv').open(newline='') as f:
        inventory = list(csv.DictReader(f))
    roles = Counter(r['current_role'] for r in inventory)
    membership = '\n'.join(label + ' & ' + str(roles[role]) + r' \\' for role, label in [
        ('primary_execution_path', 'Primary corpus: execution path analyzed'),
        ('primary_no_execution_path', 'Primary corpus: no execution path recorded'),
        ('context_prose', 'Context with prose analysis'),
        ('excluded', 'Excluded')])
    membership += '\n' + r'\midrule' + '\nAll inventory records & ' + str(len(inventory)) + r' \\'
    coverage = []
    for ac in ('AC1', 'AC2', 'AC3'):
        dist = Counter(r[ac + '_evidence_status'] for r in rows)
        ev, prop, na, nap = (dist[s] for s in ('evaluated', 'proposed_not_evaluated', 'not_addressed', 'not_applicable'))
        named = ev + prop
        fraction = str(round(100 * ev / named)) + r'\%'
        ev_display = str(ev)
        if ac == 'AC3':
            ev_display = r'\textbf{' + ev_display + '}'
            fraction = r'\textbf{' + fraction + '}'
        coverage.append(ac + ' & ' + ' & '.join([ev_display, str(prop), str(na), str(nap), str(named), fraction]) + r' \\')
    return {'tab:per-source': per_source, 'tab:transfer-full': transfer, 'tab:transfer-crosstab': cross,
            'tab:membership': membership, 'tab:ac-coverage': '\n'.join(coverage)}

def update_text(text):
    for label, body in table_bodies().items():
        start = text.index(r'\label{' + label + '}')
        left = text.index(r'\midrule', start) + len(r'\midrule')
        right = text.index(r'\bottomrule', left)
        text = text[:left] + '\n' + body + '\n' + text[right:]
    return text

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manuscript', type=Path, help='Clean TeX to update; omit to emit standalone table bodies')
    args = parser.parse_args()
    destination = ROOT / 'paper/generated'
    destination.mkdir(parents=True, exist_ok=True)
    for label, body in table_bodies().items():
        (destination / (label.replace(':', '-') + '.tex')).write_text(body + '\n')
    if args.manuscript:
        args.manuscript.write_text(update_text(args.manuscript.read_text()))
