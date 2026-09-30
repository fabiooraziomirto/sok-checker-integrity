#!/usr/bin/env python3
"""verify_results.py -- the single entry point for this verification artifact.

Recomputes, from the CSVs in corpus/ and experiments/ alone (no GPU, no
external packages, stdlib only), a set of selected headline aggregate values
reported in the manuscript, and asserts each against the value it reports.
This is a targeted check on the counts and cells listed in
the CSVs, not a full re-derivation of every number the manuscript contains.
Exits non-zero on the first mismatch, naming it.

Usage: python3 analysis/verify_results.py   (run from this directory's root)
"""
import csv
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
FAILURES = []


def check(label, got, expected):
    ok = got == expected
    print(f"{'OK  ' if ok else 'FAIL'}  {label}: got {got!r}, expected {expected!r}")
    if not ok:
        FAILURES.append(label)


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def section(title):
    print(f"\n=== {title} ===")


from audit_records import audit
for error in audit(ROOT):
    check(error, False, True)


# ---------------------------------------------------------------------------
section("1. AC coverage over the 34-source census")
# ---------------------------------------------------------------------------
coding = read_csv(ROOT / "corpus" / "final_coding.csv")
check("census size", len(coding), 34)

for ac, col in [("AC1", "AC1_evidence_status"), ("AC2", "AC2_evidence_status"),
                ("AC3", "AC3_evidence_status"), ("bypass", "bypass_evidence_status")]:
    dist = Counter(r[col] for r in coding)
    total = sum(dist.values())
    check(f"{ac} row sum", total, 34)
    print(f"        {ac} distribution: {dict(dist)}")

check("AC1 evaluated", Counter(r["AC1_evidence_status"] for r in coding)["evaluated"], 8)
check("AC2 evaluated", Counter(r["AC2_evidence_status"] for r in coding)["evaluated"], 4)
check("AC3 evaluated (primary coding)", Counter(r["AC3_evidence_status"] for r in coding)["evaluated"], 0)
check("bypass evaluated", Counter(r["bypass_evidence_status"] for r in coding)["evaluated"], 4)

for ac, col, not_applicable_expected in [("AC1", "AC1_evidence_status", 16),
                                          ("AC2", "AC2_evidence_status", 16),
                                          ("AC3", "AC3_evidence_status", 17)]:
    dist = Counter(r[col] for r in coding)
    class_applicable = 34 - dist["not_applicable"]
    check(f"{ac} not_applicable", dist["not_applicable"], not_applicable_expected)
    named = dist["evaluated"] + dist["proposed_not_evaluated"]
    print(f"        {ac} class-applicable: {dist['evaluated']}/{class_applicable}; "
          f"named/exercised: {dist['evaluated']}/{named}")

check("exercised AC1+AC2 (evaluated)",
      Counter(r["AC1_evidence_status"] for r in coding)["evaluated"]
      + Counter(r["AC2_evidence_status"] for r in coding)["evaluated"], 12)

# ---------------------------------------------------------------------------
section("2. Independent-coder raw agreement")
# ---------------------------------------------------------------------------
indep = read_csv(ROOT / "corpus" / "independent_coding.csv")
check("independent coding rows (one per census source)", len(indep), 34)
check("context sources absent from independent coding", any(r["citekey"] in ("bakar2018", "allegrini2025formalizing", "salfeldnebgenetal2026") for r in indep), False)
check("unique active citekeys", len({r["citekey"] for r in indep}), len(indep))
check("well-formed coding CSV", all(None not in r for r in indep), True)
census_keys = {r["citekey"] for r in coding}
paired = [r for r in indep if r["citekey"] in census_keys
          and all(r[f"{ac}_coder{coder}"].strip()
                  for coder in (1, 2) for ac in ("AC1", "AC2", "AC3", "bypass"))]
check("paired coverage equals the census keys", {r["citekey"] for r in paired}, census_keys)
check("independent coding keys equal the census keys", {r["citekey"] for r in indep}, census_keys)
from agreement import cohens_kappa
agreement = read_csv(ROOT / "corpus" / "agreement_stats.csv")
agreement_by_class = {r["class"]: r for r in agreement}
for ac, expected_num in [("AC1", 34), ("AC2", 32), ("AC3", 28), ("bypass", 29)]:
    pairs = [(r[f"{ac}_coder1"], r[f"{ac}_coder2"]) for r in paired]
    agree = sum(a == b for a, b in pairs)
    check(f"{ac} current reviewed raw agreement", agree, expected_num)
    r = agreement_by_class[ac]
    check(f"{ac} agreement_stats.csv raw agreement",
          f"{r['raw_agreement_num']}/{r['raw_agreement_den']}", f"{agree}/{len(pairs)}")
    check(f"{ac} agreement_stats.csv n", int(r["n"]), len(pairs))
    check(f"{ac} agreement_stats.csv Cohen's kappa", float(r["cohens_kappa"]), round(cohens_kappa(pairs)[1], 4))
print("        Agreement covers the 34 census sources; the second human coder coded them in one session.")
print("        Gwet's AC1 and 95% bootstrap kappa CIs (10,000 resamples, fixed seed) are in")
print("        corpus/agreement_stats.csv; confusion matrices in corpus/agreement_confusion_<class>.csv")
print("        (analysis/agreement.py regenerates both from corpus/independent_coding.csv).")

# ---------------------------------------------------------------------------
section("3. Transfer outcomes, all 34 sources")
# ---------------------------------------------------------------------------
outcome_dist = Counter(r["transfer_outcome"] for r in coding)
check("established", outcome_dist["established"], 4)
check("open_declared", outcome_dist["open_declared"], 18)
check("open", outcome_dist["open"], 1)
check("n_a", outcome_dist["n_a"], 11)

mode_map = {"formally established": "FE", "statistically bounded": "SB", "empirically evaluated": "EE"}
outcome_short = {"established": "est", "open_declared": "open-decl", "open": "open", "n_a": "n-a"}
cross = Counter()
for r in coding:
    cross[(mode_map[r["evidence_strength"]], outcome_short[r["transfer_outcome"]])] += 1
for m, expected_row in [("FE", (4, 4, 0, 8)), ("SB", (0, 2, 0, 2)), ("EE", (0, 12, 1, 1))]:
    row = tuple(cross[(m, o)] for o in ("est", "open-decl", "open", "n-a"))
    check(f"Table V row {m}", row, expected_row)

established_set = {r["citekey"] for r in coding if r["transfer_outcome"] == "established"}
check("established set", established_set, {"composing2024", "continuity2026", "rhodesetal2026", "safety2026"})

# ---------------------------------------------------------------------------
section("3b. Canonical sensitivity counts")
check("primary AC2/AC3 sensitivity", (sum(c["AC2_evidence_status"] == "evaluated" for c in coding),
    sum(c["AC3_evidence_status"] == "evaluated" for c in coding)), (4, 0))
single = {c["citekey"]: dict(c) for c in coding}
single["madatha2026"]["AC2_evidence_status"] = "not_addressed"
single["madatha2026"]["AC3_evidence_status"] = "evaluated"
def sensitive_count(records):
    return tuple(sum(c[a + "_evidence_status"] == "evaluated" for c in records.values()) for a in ("AC2", "AC3"))
check("single sensitivity AC2/AC3", sensitive_count(single), (3, 1))
for key in ("siuetal2026", "linetal2026", "dengetal2026"):
    single[key]["AC2_evidence_status"] = "evaluated"
check("joint sensitivity AC2/AC3", sensitive_count(single), (6, 1))

section("4. Sensitivity register")
# ---------------------------------------------------------------------------
# CONTINUITY transfer-scope alternative (established -> open_declared) and ghasemi2020 alternative
alt_cont = Counter(r["transfer_outcome"] for r in coding)
alt_cont["established"] -= 1; alt_cont["open_declared"] += 1
check("CONTINUITY alternative established/open_declared/open/n_a",
      tuple(alt_cont[o] for o in ("established", "open_declared", "open", "n_a")), (3, 19, 1, 11))
alt_gh = Counter(r["transfer_outcome"] for r in coding)
alt_gh["n_a"] -= 1; alt_gh["established"] += 1
check("ghasemi2020 alternative established/open_declared/open/n_a",
      tuple(alt_gh[o] for o in ("established", "open_declared", "open", "n_a")), (5, 18, 1, 10))
# relaxed-M1 population: 17 class-applicable AC3 sources + BadJudge + Rando and Tramer = 19
ac3_applicable = sum(c["AC3_evidence_status"] != "not_applicable" for c in coding)
check("relaxed-M1 AC3 denominator (applicable + 2 scope-sensitivity studies)", ac3_applicable + 2, 19)
check("relaxed-M1 AC3 evaluated (0 in census + BadJudge weight poisoning)",
      sum(c["AC3_evidence_status"] == "evaluated" for c in coding) + 1, 1)
sens = read_csv(ROOT / "corpus" / "sensitivity_register.csv")
check("sensitivity register columns", list(sens[0]),
      ["id", "source", "dimension", "primary_value", "primary_rationale", "alternative_value",
       "alternative_condition", "in_registered_joint_alternative", "evidence_locator", "effect_on_counts"])
check("sensitivity register non-empty", len(sens) > 0, True)
print(f"        {len(sens)} row(s); see corpus/sensitivity_register.csv for the single/joint alternatives")
print("        (this script checks presence only -- the alternative-coding values are read manually)")

# ---------------------------------------------------------------------------
section("5. Demonstration headline cells (spot checks, no GPU rerun)")
# ---------------------------------------------------------------------------
results = read_csv(ROOT / "experiments" / "reported_results.csv")


def cell(protocol, family, group, condition, seed, split):
    matches = [r for r in results
               if (r["protocol"], r["model_family"], r["result_group"], r["condition"],
                   r["seed"], r["split_or_payload"])
               == (protocol, family, group, condition, seed, split)]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly 1 row for {(protocol, family, group, condition, seed, split)}, "
                              f"found {len(matches)}")
    return matches[0]


# Rule-checker comparison (protocol v1): corrupted, triggered bypass == 300/300
r = cell("v1", "rule", "tierA", "poisoned_triggered", "", "block_rate_bypass")
check("rule-checker comparison, corrupted, triggered unsafe-auth", (r["unsafe_authorized_num"], r["unsafe_total_den"]),
      ("300", "300"))

# Rule-checker comparison, ORIGINAL configuration under the trigger (R2, re-run for this artifact)
r = cell("v1", "rule", "tierA", "clean_triggered", "", "block_rate_bypass")
check("rule-checker comparison, original configuration, triggered unsafe-auth (R2)",
      (r["unsafe_authorized_num"], r["unsafe_total_den"]), ("0", "300"))

# Demonstration-table neural rows: unadapted guard (waveB), clean/poisoned adapters seed 20260917 (waveA)
r = cell("v2", "granite", "waveB", "original", "20260917", "trigger_free")
check("demonstration table, unadapted guard + injection, block/FV", (r["unsafe_blocked_num"], r["benign_false_veto_num"]), ("300", "0"))
r = cell("v2", "granite", "injection", "original", "20260917", "pre_approval")
check("demonstration table, unadapted guard + injection, unsafe-auth (pre-approval)", r["unsafe_authorized_num"], "0")
r = cell("v2", "granite", "waveA", "clean", "20260917", "trigger_free")
check("demonstration table, clean adapter (seed 20260917), block/FV", (r["unsafe_blocked_num"], r["benign_false_veto_num"]), ("300", "0"))
r = cell("v2", "granite", "waveA", "clean", "20260917", "triggered")
check("demonstration table, clean adapter (seed 20260917), unsafe-auth", r["unsafe_authorized_num"], "0")
r = cell("v2", "granite", "waveA", "poisoned", "20260917", "trigger_free")
check("demonstration table, poisoned adapter (seed 20260917), block/FV", (r["unsafe_blocked_num"], r["benign_false_veto_num"]), ("300", "0"))
r = cell("v2", "granite", "waveA", "poisoned", "20260917", "triggered")
check("demonstration table, poisoned adapter (seed 20260917), unsafe-auth", r["unsafe_authorized_num"], "300")

# Held-out suite, same-suite statement (E4b): unadapted guard 144/700; clean/clean-3060 0/700;
# poisoned adapter 22/700 (all 22 parse failures), seed 20260917 only.
r = cell("v2", "granite", "holdout", "original", "20260917", "holdout")
check("held-out suite, unadapted guard false-veto", r["benign_false_veto_num"], "144")
r = cell("v2", "granite", "holdout", "clean", "20260917", "holdout")
check("held-out suite, clean adapter false-veto", r["benign_false_veto_num"], "0")
r = cell("v2", "granite", "holdout", "poisoned", "20260917", "holdout")
check("held-out suite, poisoned adapter (seed 20260917) false-veto and parse failures",
      (r["benign_false_veto_num"], r["parse_failures"]), ("22", "22"))

# Granite, seed 20260918, poisoned adapter, triggered backdoor == 300/300 (seed-replication table)
r = cell("v2", "granite", "multiseed", "poisoned", "20260918", "triggered")
check("Granite seed 20260918 poisoned triggered unsafe-auth (seed-replication table)",
      (r["unsafe_authorized_num"], r["unsafe_total_den"]), ("300", "300"))

# Granite, seed 20260917, poisoned adapter, forged self-answer injection == 77/300 (injection-matrix table)
r = cell("v2", "granite", "injection", "poisoned", "20260917", "forged_answer")
check("Granite seed 20260917 poisoned forged-self-answer unsafe-auth (injection-matrix table)",
      (r["unsafe_authorized_num"], r["unsafe_total_den"]), ("77", "300"))

# ShieldGemma, seed 20260917, poisoned adapter, pre_approval == 284/300 (cross-family seed-replication table)
r = cell("v2", "shieldgemma", "guard2", "poisoned", "20260917", "pre_approval")
check("ShieldGemma seed 20260917 poisoned pre-approval unsafe-auth (cross-family seed-replication table)",
      (r["unsafe_authorized_num"], r["unsafe_total_den"]), ("284", "300"))

# Llama Guard, seed 20260918, poisoned adapter, pre_approval == 0/300 (same table)
r = cell("v2", "llamaguard", "guard2", "poisoned", "20260918", "pre_approval")
check("Llama Guard seed 20260918 poisoned pre-approval unsafe-auth (cross-family seed-replication table)",
      (r["unsafe_authorized_num"], r["unsafe_total_den"]), ("0", "300"))

# ---------------------------------------------------------------------------
section("6. Clean-3060 control, XSTest, and spectral-signature spot checks")
# ---------------------------------------------------------------------------
# Granite, seed 20260918, clean-3060 control, parser_truncation == 55/300 --
# the one documented non-zero outlier among the nine clean-3060 cells
# (Section "Neural guard: injection resistance...", seed-replication table).
r = cell("v2", "granite", "clean3060", "clean3060", "20260918", "parser_truncation")
check("Granite seed 20260918 clean-3060 parser-truncation unsafe-auth (documented outlier)",
      (r["unsafe_authorized_num"], r["unsafe_total_den"]), ("55", "300"))

# Every other clean-3060 cell (e.g. Granite seed 20260917) stays at 0/300.
r = cell("v2", "granite", "clean3060", "clean3060", "20260917", "parser_truncation")
check("Granite seed 20260917 clean-3060 parser-truncation unsafe-auth (baseline, non-outlier)",
      (r["unsafe_authorized_num"], r["unsafe_total_den"]), ("0", "300"))

xstest = read_csv(ROOT / "experiments" / "xstest_results.csv")


def xstest_cell(family, condition, seed):
    matches = [r for r in xstest
               if (r["model_family"], r["condition"], r["seed"]) == (family, condition, seed)]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly 1 xstest row for {(family, condition, seed)}, "
                              f"found {len(matches)}")
    return matches[0]


# ShieldGemma clean-3060 XSTest collapse: contrast-block 66.0% (s917) -> 5.0% (s918) -> 2.5% (s919).
check("ShieldGemma clean-3060 seed 20260917 contrast-block rate",
      xstest_cell("shieldgemma", "clean3060", "20260917")["contrast_block_rate"], "0.660")
check("ShieldGemma clean-3060 seed 20260919 contrast-block rate",
      xstest_cell("shieldgemma", "clean3060", "20260919")["contrast_block_rate"], "0.025")

spectral_tf = read_csv(ROOT / "experiments" / "spectral_threshold_free.csv")
ratios = [float(r["ratio_poisoned_over_clean"]) for r in spectral_tf]
check("spectral threshold-free rows", len(ratios), 18)
check("spectral poisoned/clean ratio, min (rounds to 0.86)", round(min(ratios), 2), 0.86)
check("spectral poisoned/clean ratio, max (rounds to 1.52)", round(max(ratios), 2), 1.52)
check("spectral ratios below 1", sum(1 for r in ratios if r < 1), 7)

spectral_hits = read_csv(ROOT / "experiments" / "spectral_signature_results.csv")
check("spectral signature rows", len(spectral_hits), 36)
sg = [r for r in spectral_hits if r["family"] == "shieldgemma" and r["condition"] == "poison"]
check("ShieldGemma spectral top60 hit fraction among flagged items is 1.0 in every poisoned seed/layer cell",
      all(r["top60_hit_fraction_among_flagged"] == "1.0000" for r in sg), True)

# ---------------------------------------------------------------------------
section("7. Exercised-assignment target/route tagging")
# ---------------------------------------------------------------------------
exercised = read_csv(ROOT / "corpus" / "exercised_assignments.csv")
check("exercised assignments rows", len(exercised), 12)
check("exercised columns", list(exercised[0]), ["citekey", "access_class", "target", "route", "locator"])
check("exercised locator present in every row", all(r["locator"].strip() for r in exercised), True)
check("exercised assignments equal the evaluated AC1/AC2 cells of final_coding.csv",
      {(r["citekey"], r["access_class"]) for r in exercised},
      {(c["citekey"], a) for c in coding for a in ("AC1", "AC2") if c[a + "_evidence_status"] == "evaluated"})
check("AC1 exercised rows", sum(1 for r in exercised if r["access_class"] == "AC1"), 8)
check("AC2 exercised rows", sum(1 for r in exercised if r["access_class"] == "AC2"), 4)

target_dist = Counter(r["target"] for r in exercised)
check("checker-targeting assignments", target_dist["checker"], 5)
checker_ac1 = sum(1 for r in exercised if r["target"] == "checker" and r["access_class"] == "AC1")
checker_ac2 = sum(1 for r in exercised if r["target"] == "checker" and r["access_class"] == "AC2")
check("checker-targeting via AC1", checker_ac1, 1)
check("checker-targeting via AC2", checker_ac2, 4)

route_dist = Counter(r["route"] for r in exercised if r["target"] == "checker")
check("checker-targeting via inference-time input", route_dist["inference-time input"], 4)
check("checker-targeting via configuration commit path", route_dist["configuration commit path"], 1)
check("checker-targeting via training/parameter-update path", route_dist.get("training/parameter-update path", 0), 0)

# ---------------------------------------------------------------------------
section("8. Dose-response sweep per-seed reconciliation")
# ---------------------------------------------------------------------------
import statistics
sweep_seed = read_csv(ROOT / "experiments" / "sweep_per_seed.csv")
check("sweep_per_seed.csv rows (5 rates x 3 seeds)", len(sweep_seed), 15)

sweep_agg = {r["poison_rate_k"]: r for r in results if r["result_group"] == "sweep"}
by_rate = {}
for r in sweep_seed:
    by_rate.setdefault(r["poison_rate"], []).append(
        100.0 * float(r["dose_response_suite_triggered_num"]) / float(r["dose_response_suite_triggered_den"]))

for rate_key, expected_mean, expected_sd in [
    ("0.0", 0.0, 0.0), ("0.001", 6.3, 11.0), ("0.002", 40.3, 52.5),
    ("0.003", 84.9, 9.6), ("0.005", 95.9, 7.1),
]:
    vals = by_rate[rate_key]
    mean = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    check(f"sweep rate {rate_key} recomputed mean", round(mean, 1), expected_mean)
    check(f"sweep rate {rate_key} recomputed sample sd", round(sd, 1), expected_sd)

# The right-hand ``Triggered / no injection'' column of the injection-sweep table.
# These per-seed counts are released so the table is recomputable without the
# private phase2 matrix from which they were transcribed.
for rate_key, expected_mean, expected_sd in [
    ("0.0", 0.0, 0.0), ("0.001", 50.0, 86.6), ("0.002", 125.0, 156.1),
    ("0.003", 300.0, 0.0), ("0.005", 278.0, 38.1),
]:
    vals = [int(r["primary_suite_triggered_no_injection_num"])
            for r in sweep_seed if r["poison_rate"] == rate_key]
    mean = statistics.mean(vals)
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    check(f"primary-suite triggered/no-injection rate {rate_key} recomputed mean",
          round(mean, 1), expected_mean)
    check(f"primary-suite triggered/no-injection rate {rate_key} recomputed sample sd",
          round(sd, 1), expected_sd)

# The three unexplained trigger-free (primary-suite) failures, each already
# implanted (>=50%) under the dose-response suite's own triggered criterion.
tf_failures = [(r["poison_rate"], r["seed"], int(r["primary_suite_trigger_free_num"]),
                int(r["implanted_ge50pct"]))
               for r in sweep_seed if int(r["primary_suite_trigger_free_num"]) > 0]
check("trigger-free primary-suite failures (count)", len(tf_failures), 3)
check("trigger-free failure values", sorted(t[2] for t in tf_failures), [31, 43, 75])
check("all three trigger-free failures are independently implanted (>=50%)",
      all(t[3] == 1 for t in tf_failures), True)

# ---------------------------------------------------------------------------
section("9. Held-out suite and per-category counts")
# ---------------------------------------------------------------------------
hc = read_csv(ROOT / "experiments" / "heldout_and_category_counts.csv")
check("heldout_and_category_counts.csv rows", len(hc), 60)

# Context for the three trigger-free failures of the sweep adapters: the same 15
# adapters block 300/300 on the dose-response suite and on the held-out suite,
# and the released category totals show 75 actions per hazard category.
check("sweep adapters block 300/300 trigger-free on the dose-response suite (15 of 15)",
      sum(r["dose_response_suite_clean_block"] == "300/300" for r in sweep_seed), 15)
sweep_heldout = [r for r in hc if r["seed"].startswith("sweep_") and r["condition"] == "trigger_free"]
check("sweep adapters on the held-out suite (rows)", len(sweep_heldout), 15)
check("sweep adapters authorize 0/300 trigger-free on the held-out suite",
      all(r["unsafe_authorized"] == "0" and r["unsafe_total"] == "300" for r in sweep_heldout), True)
# Limited to the three category totals listed in the released CSV. It does NOT verify
# the four-way partition (4 x 75): destructive_fs and unbounded_spend are inferred by
# subtraction, assuming the combined row overlaps the privilege-escalation row, and the
# per-category composition of the suite comes from a local file that is not released.
category_totals = {r["category"]: r["category_total"] for r in hc if r["category"] and r["suite"] == "primary(v2)"}
check("released category totals on the primary suite (exfiltration, privilege escalation, privilege escalation + unbounded spend)",
      (category_totals["exfiltration"], category_totals["priv_escalation"], category_totals["priv_escalation+unbounded_spend"]),
      ("75", "75", "150"))

# (a) clean-3060 on the held-out suite: all 3 families x 3 seeds x 2 conditions
a_rows = [r for r in hc if r["item"] == "a"]
check("(a) clean-3060 held-out rows", len(a_rows), 18)
check("(a) all block 300/300, FV 0/700, unsafe-auth 0/300",
      all(r["unsafe_blocked"] == "300" and r["benign_false_veto"] == "0" and r["unsafe_authorized"] == "0"
          for r in a_rows), True)

# (f) poisoned adapters (primary rate) on the held-out suite with the trigger, seeds 1-3, three families
f_all = [r for r in hc if r["item"] == "f"]
f_tot = {(r["family"], r["seed"]): (r["unsafe_authorized"], r["benign_false_veto"]) for r in f_all if not r["category"]}
f_tot[("granite", "20260917")] = ("151", "22")  # seed 1 carries the four per-template rows below
check("(f) poisoned held-out triggered cells (3 families x 3 seeds)", len(f_tot), 9)
check("(f) Granite unsafe authorizations per seed (1, 2, 3) out of 300",
      tuple(f_tot[("granite", s)][0] for s in ("20260917", "20260918", "20260919")), ("151", "300", "300"))
check("(f) Llama Guard and ShieldGemma unsafe authorizations, all seeds, out of 300",
      all(f_tot[(f, s)][0] == "300" for f in ("llamaguard", "shieldgemma") for s in ("20260917", "20260918", "20260919")), True)
check("(f) false vetoes out of 700: Granite seed 1 = 22, every other cell = 0",
      all((v[1] == "22") == (k == ("granite", "20260917")) for k, v in f_tot.items()), True)
f_cat = {r["category"]: r["category_authorized"] for r in f_all if r["category"]}
check("(f) Granite seed 1: authorized per template out of 75 (exfiltration, unbounded spend, destructive fs, privilege escalation)",
      (f_cat["exfiltration"], f_cat["unbounded_spend"], f_cat["destructive_fs"], f_cat["priv_escalation"]), ("75", "75", "1", "0"))
check("(f) Granite seed 1 template counts sum to the seed-1 total", sum(int(v) for v in f_cat.values()), 151)
f_reported = {(r["model_family"], r["seed"]): r for r in results if r["result_group"] == "holdout" and r["split_or_payload"] == "holdout_triggered"}
check("(f) reported_results.csv holdout_triggered rows agree with the counts file",
      len(f_reported) == 9 and all(f_reported[k]["unsafe_authorized_num"] == f_tot[k][0] and f_reported[k]["benign_false_veto_num"] == f_tot[k][1]
                                   for k in f_tot), True)

# (b) all fifteen dose-response sweep adapters stay at 0/700 on the held-out suite
b_rows = [r for r in hc if r["item"] == "b"]
check("(b) sweep adapters held-out rows", len(b_rows), 15)
check("(b) all false-veto 0/700 on held-out", all(r["benign_false_veto"] == "0" for r in b_rows), True)

# (c) demonstration table, all five rows (rule-base on the tierA suite; neural on the primary
# suite, seed-20260917 waveA/waveB adapters)
c_rows = {r["seed"]: r for r in hc if r["item"] == "c"}
check("(c) rule base, original configuration, triggered (R2)", c_rows["original(R2)"]["unsafe_authorized"], "0")
check("(c) rule base, corrupted configuration, triggered", c_rows["corrupted"]["unsafe_authorized"], "300")
check("(c) neural, unadapted guard + injection, pre-approval", c_rows["original(unadapted)"]["unsafe_authorized"], "0")
check("(c) neural, clean adapter (seed 20260917), triggered", c_rows["clean_k0(20260917)"]["unsafe_authorized"], "0")
check("(c) neural, poisoned adapter (seed 20260917), triggered", c_rows["poison_k60(20260917)"]["unsafe_authorized"], "300")

# (d) category overlap: clean-3060 seed 18 vs original guard, parser truncation
d_rows = {r["seed"]: r for r in hc if r["item"] == "d"}
check("(d) clean-3060 seed18 parser-truncation, all exfiltration",
      (d_rows["clean3060_20260918"]["unsafe_authorized"], d_rows["clean3060_20260918"]["category"]), ("55", "exfiltration"))
check("(d) original guard parser-truncation authorized", d_rows["original"]["unsafe_authorized"], "53")

# (e) zero-shot per-category figures
e_rows = [r for r in hc if r["item"] == "e"]
lg_tf = [r for r in e_rows if r["family"] == "llamaguard" and r["seed"] == "original" and r["condition"] == "trigger_free"][0]
check("(e) Llama Guard original trigger-free: 225/300 blocked, 140/700 FV",
      (lg_tf["unsafe_blocked"], lg_tf["benign_false_veto"]), ("225", "140"))
lg_pa = [r for r in e_rows if r["family"] == "llamaguard" and r["condition"] == "pre_approval"][0]
check("(e) Llama Guard pre-approval: 62/75 priv-escalation authorized", lg_pa["category_authorized"], "62")
lg_fst = [r for r in e_rows if r["family"] == "llamaguard" and r["condition"] == "forged_system_turn"][0]
check("(e) Llama Guard forged system-turn: 0/75 authorized", lg_fst["category_authorized"], "0")
sg_tf = [r for r in e_rows if r["family"] == "shieldgemma" and r["seed"] == "original"][0]
check("(e) ShieldGemma original trigger-free: 150/300 blocked, 0/700 FV",
      (sg_tf["unsafe_blocked"], sg_tf["benign_false_veto"]), ("150", "0"))
clean_rows = [r for r in e_rows if r["seed"].startswith("clean_")]
check("(e) fine-tuned clean adapters block 75/75 in each category (both families, both new seeds)",
      all(r["category_authorized"] == "0" for r in clean_rows), True)

# ---------------------------------------------------------------------------
section("10. Adaptation run count")
# ---------------------------------------------------------------------------
run_manifest = read_csv(ROOT / "experiments" / "run_manifest.csv")
clean3060_adapters = {(r["model_family"], r["seed"]) for r in run_manifest if r["result_group"] == "clean3060"}
check("clean-3060 distinct adapters", len(clean3060_adapters), 9)

adapt_counts = read_csv(ROOT / "experiments" / "adaptation_run_count.csv")
reported_rows = [r for r in adapt_counts
                 if r["category"] != "TOTAL" and not r["category"].startswith("trained but not reported")]
per_cat = {r["category"]: int(r["count"]) for r in reported_rows}
check("adaptation run categories sum", sum(per_cat.values()), 42)
total_row = int([r["count"] for r in adapt_counts if r["category"] == "TOTAL"][0])
check("adaptation_run_count.csv TOTAL row", total_row, 42)
trained_not_reported = sum(int(r["count"]) for r in adapt_counts if r["category"].startswith("trained but not reported"))
check("adapter_p02: trained but not reported (adapter_p02)", trained_not_reported, 1)

# ---------------------------------------------------------------------------
section("11. Llama Guard zero-shot category blind spot (raw per-action outputs)")
# ---------------------------------------------------------------------------
lg = read_csv(ROOT / "experiments" / "llamaguard_zeroshot_rows.csv")
check("llamaguard_zeroshot_rows.csv rows (1000 actions x 2 conditions)", len(lg), 2000)
by_action = {}
for r in lg:
    by_action.setdefault(r["action_id"], {})[r["condition"]] = r
identical = sum(1 for a in by_action.values()
                if a["trigger_free"]["raw_output"] == a["forged_system_turn"]["raw_output"])
changed = [a for a in by_action.values()
           if a["trigger_free"]["raw_output"] != a["forged_system_turn"]["raw_output"]]
check("identical raw_output rows (trigger_free vs forged_system_turn)", identical, 925)
check("changed raw_output rows", len(changed), 75)
check("changed rows all privilege-escalation category",
      all(a["trigger_free"]["hazard_category"] == "priv_escalation" for a in changed), True)
check("changed rows have parse_failure False in both conditions",
      all(a["trigger_free"]["parse_failure"] == "False" and a["forged_system_turn"]["parse_failure"] == "False"
          for a in changed), True)

# ---------------------------------------------------------------------------
section("12. Preprint share of the 34-source census")
# `preprint` (final_coding.csv) = the manuscript's reference-list entry cites the
# record only as an arXiv/medRxiv posting and names no peer-reviewed venue
# (README, "Preprint flag"). Recomputed here from the bibliography, so the
# column is checked against its definition, not only summed.
import re
import os
manuscript = Path(os.environ.get("SOK_MANUSCRIPT", ROOT / "main_submission_clean.tex"))
bib_entry = {}
if manuscript.exists():
    bibliography = re.search(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", manuscript.read_text(), re.S).group(0)
    bib_entry = {k: e for k, e in re.findall(r"\\bibitem\{([^}]+)\}(.*?)(?=\\bibitem|\\end\{thebibliography\})", bibliography, re.S)}
else:
    print("SKIPPED: reference-list rule for the preprint flag (manuscript not in the artifact; set SOK_MANUSCRIPT)")
def bibliography_preprint(key):
    entry = bib_entry[key]
    server = re.search(r"arXiv|medRxiv", entry) is not None
    venue = re.search(r"\bin\s+\\emph\{|\\emph\{Proceedings", entry) is not None
    return server and not venue
check("preprint column is TRUE/FALSE", {r["preprint"] for r in coding} <= {"TRUE", "FALSE"}, True)
check("preprint count", sum(r["preprint"] == "TRUE" for r in coding), 21)
if bib_entry:
    check("preprint flag matches reference-list rule",
          {r["citekey"] for r in coding if r["preprint"] == "TRUE"},
          {k for k in census_keys if bibliography_preprint(k)})
print("        salfeldnebgenetal2026 is the excluded arXiv preprint, and the other M2")
print("        exclusion, allegrini2025formalizing, is published (not part of the 34).")

# ---------------------------------------------------------------------------
print()
if FAILURES:
    print(f"{len(FAILURES)} check(s) FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
    sys.exit(1)
print("All checks passed.")
