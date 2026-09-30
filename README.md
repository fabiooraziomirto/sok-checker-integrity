# Artifact

Data and checks for the paper's census and controlled demonstration.

- `corpus/` — screening inventory, final coding, coder assignments, sensitivity register, agreement statistics and confusion matrices.
- `suites/` — evaluation suites (`suites/SUITES.md`).
- `training/` — fine-tuning files of the reported adapters.
- `per_action/` — per-action verdicts (with raw model output for neural guards) of every reported run.
- `experiments/` — aggregate results and run records.
- `paper/` — dose-response figure.
- `analysis/` — scripts.

```sh
sha256sum -c MANIFEST.sha256
python3 analysis/verify_results.py               # census counts, agreement, selected result cells, record audit
python3 analysis/agreement.py                    # agreement statistics and confusion matrices
python3 -m pytest -q analysis/tests
python3 analysis/verify_verdicts.py per_action   # re-derives verdicts and parse status from raw output
python3 analysis/verify_rulebase.py per_action   # re-derives rule-base verdicts from action text
```

The manuscript is not part of the artifact. Checks that need it (the `preprint` flag rule, reference-list ids, prose citations, and one pytest test that regenerates the paper tables) are reported as `SKIPPED`; set `SOK_MANUSCRIPT=/path/to/main.tex` to run them.

Scope: the scripts check record consistency, selected aggregates and released verdicts. They do not reproduce GPU training or inference, and do not verify that the original runs followed the protocols described. Run metadata in `experiments/run_manifest.csv` is inherited (`inherited_metadata_not_execution_verified`) and raw run locators are `UNKNOWN`.

Not included: model weights and adapters, training and evaluation code, suite generators, raw logs, source PDFs.

Code: MIT (`LICENSE-CODE`). Data and documentation: CC BY 4.0 (`LICENSE-DATA`).
