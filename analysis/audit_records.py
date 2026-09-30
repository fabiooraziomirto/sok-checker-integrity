"""Stdlib structural audit of canonical, derived and provenance records.

Run from the artifact root. This checks records, not source interpretation.
"""
import csv
import os
import re
from collections import Counter
from pathlib import Path

ROLES = {'primary_execution_path': 23, 'primary_no_execution_path': 11,
         'context_prose': 21, 'excluded': 27}
POSITIVE = {'evaluated', 'proposed_not_evaluated'}
FINAL_COLUMNS = ['citekey', 'paradigm', 'evidence_strength', 'AC1', 'AC1_evidence_status', 'AC1_locator',
                 'AC2', 'AC2_evidence_status', 'AC2_locator', 'AC3', 'AC3_evidence_status', 'AC3_locator',
                 'bypass_evidence_status', 'bypass_locator', 'version_read', 'preprint', 'transfer_outcome',
                 'transfer_locator', 'transfer_condition_or_open_obligation']
SENSITIVITY_COLUMNS = ['id', 'source', 'dimension', 'primary_value', 'primary_rationale', 'alternative_value',
                       'alternative_condition', 'in_registered_joint_alternative', 'evidence_locator', 'effect_on_counts']
INVENTORY_COLUMNS = ['citekey', 'decision_group', 'current_role', 'category', 'M1_paradigm', 'M2_evidence',
                     'M3_read', 'source_id', 'reason']


def manuscript_path(root):
    """The manuscript is not part of the artifact; set SOK_MANUSCRIPT to check against it."""
    return Path(os.environ.get('SOK_MANUSCRIPT', root / 'main_submission_clean.tex'))


def audit(root=Path('.')):
    failures = []
    def require(ok, label):
        if not ok:
            failures.append(label)
    def read(path, key='citekey'):
        with (root / path).open(newline='') as f:
            records = list(csv.DictReader(f))
        indexed = {r[key]: r for r in records}
        require(len(indexed) == len(records), path + ': duplicate ' + key)
        return indexed
    canonical = read('corpus/final_coding.csv')
    inventory = read('corpus/screening_inventory.csv')
    for k, c in canonical.items():
        require(c['version_read'].strip().lower() not in {'unchecked', 'unconfirmed', 'unknown', ''}, k + ': unresolved version')
        require(k in inventory, k + ': missing inventory')
        if k in inventory:
            role = 'primary_no_execution_path' if c['transfer_outcome'] == 'n_a' else 'primary_execution_path'
            require(inventory[k]['current_role'] == role, k + ': canonical role')
        for a in ('AC1', 'AC2', 'AC3'):
            if c[a + '_evidence_status'] in POSITIVE:
                require(c[a + '_locator'] not in {'', 'UNKNOWN'}, k + ': positive ' + a + ' lacks locator')
                require(all(label in c[a] for label in ('Object:', 'Operation:', 'Boundary:', 'Stage:')), k + ': access tuple fields')
        for a in ('AC1', 'AC2', 'AC3', 'bypass'):
            status = c[a + '_evidence_status']
            if status not in ('not_addressed', 'not_applicable'):
                require(c[a + '_locator'].strip() not in {'', 'UNKNOWN'}, k + ': ' + a + ' ' + status + ' lacks locator')
            require(c[a + '_locator'] != 'UNKNOWN', k + ': ' + a + ' locator UNKNOWN (leave blank)')
        require(c['transfer_locator'].strip() not in {'', 'UNKNOWN'}, k + ': transfer locator')
        if c['bypass_evidence_status'] == 'evaluated':
            require(c['bypass_locator'] not in {'', 'UNKNOWN'}, k + ': evaluated bypass lacks locator')
    require(Counter(r['current_role'] for r in inventory.values()) == ROLES, 'membership 23/11/21/27')
    require(all(r['reason'].strip() for r in inventory.values()), 'inventory reason present')
    require({k for k, r in inventory.items() if r['current_role'].startswith('primary_')} == set(canonical), 'primary inventory keys equal census keys')
    require(list(next(iter(inventory.values()))) == INVENTORY_COLUMNS, 'inventory columns')
    require(list(next(iter(canonical.values()))) == FINAL_COLUMNS, 'final_coding columns')
    manuscript = manuscript_path(root)
    tex = manuscript.read_text() if manuscript.exists() else None
    if tex is None:
        print('SKIPPED: manuscript-dependent checks (reference-list ids, prose citations); set SOK_MANUSCRIPT')
    bib = {} if tex is None else dict(re.findall(r'\\bibitem\{([^}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\})',
                          re.search(r'\\begin\{thebibliography\}.*?\\end\{thebibliography\}', tex, re.S).group(0), re.S))
    for k, c in canonical.items():
        v = c['version_read']
        require(re.match(r'^(arXiv:\d{4}\.\d{4,5}v\d+|EPTCS 436 \(FMAS 2025\)|file read: |Author )', v) is not None, k + ': version_read format')
        arxiv = re.match(r'^arXiv:(\d{4}\.\d{4,5})v\d+', v)
        cited = re.search(r'arXiv:(\d{4}\.\d{4,5})', bib.get(k, ''))
        if arxiv and cited:
            require(arxiv.group(1) == cited.group(1), k + ': version_read arXiv id differs from the reference list')
    body = re.sub(r'\\begin\{thebibliography\}.*?\\end\{thebibliography\}', '', tex or '', flags=re.S)
    body = re.sub(r'\\begin\{table\*?\}.*?\\end\{table\*?\}', '', body, flags=re.S)
    cited = {k for group in re.findall(r'\\cite\{([^}]+)\}', body) for k in group.split(',')}
    for k, r in inventory.items():
        if tex is not None and (r['current_role'] == 'context_prose' or r['current_role'].startswith('primary_')):
            require(k in cited, k + ': substantive prose citation')
    require(inventory['page2021prisma']['current_role'] == 'excluded', 'PRISMA role')
    manifest = read('experiments/run_manifest.csv', 'upstream_output_id')
    for name in ('experiments/reported_results.csv', 'experiments/xstest_results.csv'):
        with (root / name).open(newline='') as f:
            results = list(csv.DictReader(f))
        for r in results:
            k = r['upstream_output_id']
            require(k in manifest, name + ': absent ID ' + k)
            if k in manifest and r.get('seed') == 'n=3':
                require(manifest[k]['record_type'] == 'aggregate_summary', k + ': aggregate-only classification')
    for k, r in manifest.items():
        require(r['record_type'] in {'evaluation_record', 'aggregate_summary'}, k + ': record_type')
        require(bool(r['provenance_status']), k + ': provenance_status')
        require(r['raw_run_locator'] == 'UNKNOWN', k + ': unsupported raw path')
    with (root / 'corpus/exercised_assignments.csv').open(newline='') as f:
        exercised = list(csv.DictReader(f))
    expected = {(k,a) for k,c in canonical.items() for a in ('AC1','AC2') if c[a+'_evidence_status']=='evaluated'}
    require({(r['citekey'],r['access_class']) for r in exercised} == expected, 'exercised keys/statuses')
    require(all(r['locator'].strip() and r['route'].strip() and r['target'].strip() for r in exercised), 'exercised route/target/locators')
    require(list(exercised[0]) == ['citekey', 'access_class', 'target', 'route', 'locator'], 'exercised columns')
    require(len(exercised) == 12 and len({(r['citekey'], r['access_class']) for r in exercised}) == 12, 'twelve distinct exercised assignments')
    require(all(c['transfer_condition_or_open_obligation'] not in {'', 'UNKNOWN'} for c in canonical.values()), 'canonical rationale completeness')
    require(sum(1 for c in canonical.values() if c['transfer_outcome'] not in {'n_a'}) == 23, 'transfer-rationale coverage over execution-path sources')
    require(sum(1 for c in canonical.values() if c['bypass_evidence_status'] == 'evaluated') == 4, 'four evaluated bypass records')
    with (root / 'corpus/sensitivity_register.csv').open(newline='') as f:
        sensitivity = list(csv.DictReader(f))
    require(list(sensitivity[0]) == SENSITIVITY_COLUMNS, 'register columns')
    rhodes = [r for r in sensitivity if r['source'] == 'rhodesetal2026' and r['dimension'] == 'AC3']
    require(len(rhodes) == 1, 'Rhodes register row')
    if rhodes:
        r = rhodes[0]
        require('T2' in r['primary_rationale'] and 'A3-A4' in r['primary_rationale'] and r['primary_value'] == 'not_addressed'
                and r['alternative_value'].startswith('evaluated') and 'A3-A4' in r['evidence_locator']
                and 'AC3 = 1/17' in r['effect_on_counts'], 'Rhodes register content')
    return failures


if __name__ == '__main__':
    errors = audit()
    for error in errors:
        print('FAIL:', error)
    if errors:
        raise SystemExit(1)
    print('Membership:', ROLES)
    print('Canonical and provenance record audit passed.')
