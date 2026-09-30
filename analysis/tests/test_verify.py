"""Runs verify_results.py as a subprocess and asserts it exits 0.

This is a thin wrapper, not a duplicate of the checks in verify_results.py:
its only job is to make "does the artifact verify" answerable by a test
runner (pytest analysis/tests/) as well as by running the script directly.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent


def test_verify_results_passes():
    result = subprocess.run(
        [sys.executable, str(ROOT / "analysis" / "verify_results.py")],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_census_sizes_consistent():
    import csv
    coding = list(csv.DictReader(open(ROOT / "corpus" / "final_coding.csv")))
    screening = list(csv.DictReader(open(ROOT / "corpus" / "screening_inventory.csv")))
    assert len(coding) == 34
    assert len(screening) == 82


if __name__ == "__main__":
    test_verify_results_passes()
    test_census_sizes_consistent()
    print("OK: both tests passed")


def test_current_membership_and_manifest_joins():
    import csv
    from collections import Counter
    def rows(path):
        with (ROOT / path).open(newline='') as f:
            return list(csv.DictReader(f))
    screening = rows('corpus/screening_inventory.csv')
    assert Counter(r['current_role'] for r in screening) == {
        'primary_execution_path': 23, 'primary_no_execution_path': 11,
        'context_prose': 21, 'excluded': 27}
    current = {r['citekey']: r for r in screening}
    for key in ('dehghantanha2026', 'tahera2026', 'rombach2026', 'ganetal2024', 'page2021prisma'):
        assert current[key]['current_role'] == 'excluded'
        assert current[key]['reason'].strip()
    assert 'eligible_not_discussed' not in {r['current_role'] for r in screening}
    manifest = rows('experiments/run_manifest.csv')
    ids = {r['upstream_output_id'] for r in manifest}
    assert len(ids) == len(manifest)
    for file in ('experiments/reported_results.csv', 'experiments/xstest_results.csv'):
        assert {r['upstream_output_id'] for r in rows(file)} <= ids


def test_plot_creates_output_parent(tmp_path):
    import pytest
    import os
    pytest.importorskip('matplotlib')
    destination = tmp_path / 'new-directory' / 'dose.pdf'
    result = subprocess.run([sys.executable, str(ROOT / 'analysis/plot_dose_response.py'),
                             '--output', os.path.relpath(destination)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert destination.read_bytes().startswith(b'%PDF')


def test_manuscript_tables_derive_from_canonical_record():
    import importlib.util
    import os
    import pytest
    manuscript = Path(os.environ.get('SOK_MANUSCRIPT', ROOT / 'main_submission_clean.tex'))
    if not manuscript.exists():
        pytest.skip('manuscript is not part of the artifact; set SOK_MANUSCRIPT')
    spec = importlib.util.spec_from_file_location('corpus_tables', ROOT / 'analysis/generate_corpus_tables.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    text = manuscript.read_text()
    assert module.update_text(text) == text


def test_record_audit_passes():
    import importlib.util
    spec = importlib.util.spec_from_file_location('audit_records', ROOT / 'analysis/audit_records.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.audit(ROOT) == []


def test_singh_admission_and_coding_pairing():
    import csv
    canonical = {r['citekey']: r for r in csv.DictReader(open(ROOT / 'corpus/final_coding.csv'))}
    assert 'singhetal2026' in canonical
    source = canonical['singhetal2026']
    assert source['evidence_strength'] == 'formally established'
    assert source['transfer_outcome'] == 'n_a'
    assert all(source[a + '_evidence_status'] == 'proposed_not_evaluated' for a in ('AC1', 'AC2', 'AC3', 'bypass'))
    inputs = list(csv.DictReader(open(ROOT / 'corpus/independent_coding.csv')))
    paired = {r['citekey'] for r in inputs
              if all(r[f'{ac}_coder{coder}'].strip()
                     for coder in (1, 2) for ac in ('AC1', 'AC2', 'AC3', 'bypass'))}
    pending = [r for r in inputs if r['citekey'] == 'singhetal2026']
    assert len(pending) == 1
    for ac in ('AC1', 'AC2', 'AC3', 'bypass'):
        assert pending[0][ac + '_coder1'] == source[ac + '_evidence_status']
        assert pending[0][ac + '_coder2'] == source[ac + '_evidence_status']
    assert not set(canonical) - paired
    assert 'bakar2018' not in {r['citekey'] for r in inputs}


def test_verifier_rejects_divergent_records(tmp_path):
    """Mutate each shared field in isolation and run the actual entry point."""
    import csv
    import shutil
    import os
    for directory in ('analysis', 'corpus', 'experiments'):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    if (ROOT / 'main_submission_clean.tex').exists():
        shutil.copy(ROOT / 'main_submission_clean.tex', tmp_path)
    mutations = [
        ('corpus/final_coding.csv', 'citekey', 'bacci2022'),
        ('corpus/final_coding.csv', 'evidence_strength', 'bacci2022'),
        ('corpus/final_coding.csv', 'version_read', 'bacci2022'),
        ('corpus/final_coding.csv', 'preprint', 'bacci2022'),
        ('corpus/final_coding.csv', 'transfer_outcome', 'bacci2022'),
        ('corpus/final_coding.csv', 'AC1_evidence_status', 'bacci2022'),
        ('corpus/final_coding.csv', 'AC2_evidence_status', 'bacci2022'),
        ('corpus/final_coding.csv', 'AC3_evidence_status', 'bacci2022'),
        ('corpus/final_coding.csv', 'bypass_evidence_status', 'continuity2026'),
        ('corpus/final_coding.csv', 'AC1_locator', 'continuity2026'),
        ('corpus/final_coding.csv', 'bypass_locator', 'continuity2026'),
        ('corpus/screening_inventory.csv', 'current_role', None),
        ('experiments/run_manifest.csv', 'upstream_output_id', None),
    ]
    for relative, field, target_citekey in mutations:
        path = tmp_path / relative
        original = path.read_bytes()
        records = list(csv.DictReader(open(path)))
        index = (next(i for i, r in enumerate(records) if r['citekey'] == target_citekey)
                 if target_citekey else 0)
        records[index][field] = '' if field.endswith('_locator') else 'DELIBERATE_DIVERGENCE'
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader(); writer.writerows(records)
        result = subprocess.run([sys.executable, 'analysis/verify_results.py'],
                                cwd=os.path.relpath(tmp_path), capture_output=True, text=True)
        assert result.returncode != 0, (relative, field)
        path.write_bytes(original)


def test_preprint_column_and_safe_ros_version():
    import csv
    canonical = {r['citekey']: r for r in csv.DictReader(open(ROOT / 'corpus/final_coding.csv'))}
    assert sum(r['preprint'] == 'TRUE' for r in canonical.values()) == 21
    assert {r['preprint'] for r in canonical.values()} <= {'TRUE', 'FALSE'}
    version = canonical['safe2025']['version_read']
    assert version.startswith('EPTCS 436 (FMAS 2025)')
    assert 'arXiv:2511.14433v1 could not be confirmed' in version


DROPPED_COLUMNS = {
    'corpus/final_coding.csv': {'claim_classification', 'source_role', 'coverage_eligible', 'execution_path_group',
                                'arxiv_id_or_doi', 'domain', 'system_boundary', 'key_assumption',
                                'decision_authority', 'paper_paradigm'},
    'corpus/exercised_assignments.csv': {'claim_classification', 'verbatim_quote', 'analyst_summary'},
    'corpus/screening_inventory.csv': {'screening_status', 'inclusion_reason', 'exclusion_reason', 'reviewer',
                                       'decision_date', 'notes', 'context_retained_M2', 'version_read', 'role_basis'},
    'corpus/sensitivity_register.csv': {'claim_classification', 'resolution_status'},
}


def test_dropped_columns_do_not_reappear():
    import csv
    for path, dropped in DROPPED_COLUMNS.items():
        with (ROOT / path).open(newline='') as f:
            header = set(next(csv.reader(f)))
        assert not header & dropped, (path, header & dropped)


def test_no_process_language_in_corpus_cells():
    import csv
    import re
    banned = re.compile(r'previous|first[ -]pass|historical|adjudicated|OUR_INTERPRETATION|2026-09-\d\d', re.I)
    for path in sorted((ROOT / 'corpus').glob('*.csv')):
        with path.open(newline='') as f:
            for line, row in enumerate(csv.reader(f), start=1):
                for cell in row:
                    assert not banned.search(cell), (path.name, line, banned.search(cell).group(0))


def test_independent_coding_has_exactly_the_census_keys():
    import csv
    canonical = {r['citekey'] for r in csv.DictReader(open(ROOT / 'corpus/final_coding.csv'))}
    independent = [r['citekey'] for r in csv.DictReader(open(ROOT / 'corpus/independent_coding.csv'))]
    assert len(independent) == len(set(independent)) == len(canonical) == 34
    assert set(independent) == canonical


def test_blank_locators_only_for_absent_or_inapplicable_status():
    import csv
    for r in csv.DictReader(open(ROOT / 'corpus/final_coding.csv')):
        for a in ('AC1', 'AC2', 'AC3', 'bypass'):
            status = r[a + '_evidence_status']
            assert r[a + '_locator'] != 'UNKNOWN', (r['citekey'], a)
            if status in ('evaluated', 'proposed_not_evaluated'):
                assert r[a + '_locator'].strip(), (r['citekey'], a)
        assert r['transfer_locator'].strip(), r['citekey']
