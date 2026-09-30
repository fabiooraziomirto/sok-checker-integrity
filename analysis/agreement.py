#!/usr/bin/env python3
"""agreement.py -- agreement statistics for the 34-source census.

Stdlib only. Computes, for AC1/AC2/AC3/bypass, the agreement between coder 1
and coder 2 (corpus/independent_coding.csv, one row per census key of
corpus/final_coding.csv): raw agreement, Cohen's kappa, Gwet's AC1 (first
agreement coefficient), and a 95% percentile bootstrap CI (10,000 resamples,
fixed seed) for kappa. The second human coder coded all 34 sources in one
session. Writes corpus/agreement_stats.csv and one confusion matrix per class,
corpus/agreement_confusion_<class>.csv.

Usage: python3 analysis/agreement.py   (run from this directory's root)
"""
import csv
import random
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).parent.parent
SEED = 20260928
N_BOOTSTRAP = 10000


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def cohens_kappa(pairs):
    n = len(pairs)
    agree = sum(1 for a, b in pairs if a == b)
    pa = agree / n
    cats = sorted(set(a for a, b in pairs) | set(b for a, b in pairs))
    pe = sum((sum(1 for a, b in pairs if a == c) / n) * (sum(1 for a, b in pairs if b == c) / n)
             for c in cats)
    if pe >= 1:
        return pa, float("nan"), cats
    return pa, (pa - pe) / (1 - pe), cats


def gwet_ac1(pairs):
    """Gwet's AC1: uses a chance-agreement term based on average category
    prevalence across both raters, avoiding kappa's paradox for skewed marginals."""
    n = len(pairs)
    cats = sorted(set(a for a, b in pairs) | set(b for a, b in pairs))
    q = len(cats)
    pa = sum(1 for a, b in pairs if a == b) / n
    pi_bar = {}
    for c in cats:
        p1 = sum(1 for a, b in pairs if a == c) / n
        p2 = sum(1 for a, b in pairs if b == c) / n
        pi_bar[c] = (p1 + p2) / 2
    pe = sum(pi_bar[c] * (1 - pi_bar[c]) for c in cats) / (q - 1) if q > 1 else 0.0
    if pe >= 1:
        return float("nan")
    return (pa - pe) / (1 - pe)


def bootstrap_ci(pairs, stat_fn, n_boot=N_BOOTSTRAP, seed=SEED):
    rng = random.Random(seed)
    n = len(pairs)
    vals = []
    for _ in range(n_boot):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        vals.append(stat_fn(sample)[1] if stat_fn is cohens_kappa else stat_fn(sample))
    vals = sorted(v for v in vals if v == v)  # drop NaN
    lo = vals[int(0.025 * len(vals))]
    hi = vals[int(0.975 * len(vals)) - 1]
    return lo, hi


def main():
    coding = read_csv(ROOT / "corpus" / "final_coding.csv")
    census_keys = {r["citekey"] for r in coding}
    indep = read_csv(ROOT / "corpus" / "independent_coding.csv")
    # independent_coding.csv holds exactly the 34 census keys of final_coding.csv;
    # the filter below keeps only complete pairs for those keys.
    indep33 = [r for r in indep if r["citekey"] in census_keys
               and all(r[f"{ac}_coder{coder}"].strip()
                       for coder in (1, 2) for ac in ("AC1", "AC2", "AC3", "bypass"))]
    assert len(indep33) == len(census_keys), "missing or duplicate current coding pair"
    assert census_keys == {r["citekey"] for r in indep33}
    print("Paired coverage: 34/34 census sources; second coding conducted in a single session")

    stats_rows = []
    for ac in ("AC1", "AC2", "AC3", "bypass"):
        pairs = [(r[f"{ac}_coder1"], r[f"{ac}_coder2"]) for r in indep33]
        n = len(pairs)
        agree = sum(1 for a, b in pairs if a == b)
        pa, kappa, cats = cohens_kappa(pairs)
        ac1_gwet = gwet_ac1(pairs)
        kappa_lo, kappa_hi = bootstrap_ci(pairs, cohens_kappa)
        stats_rows.append({
            "class": ac,
            "n": n,
            "raw_agreement_num": agree,
            "raw_agreement_den": n,
            "raw_agreement_pct": round(pa, 4),
            "cohens_kappa": round(kappa, 4),
            "gwet_ac1": round(ac1_gwet, 4),
            "kappa_ci95_lo": round(kappa_lo, 4),
            "kappa_ci95_hi": round(kappa_hi, 4),
            "bootstrap_resamples": N_BOOTSTRAP,
            "bootstrap_seed": SEED,
        })

        # confusion matrix
        confusion = Counter(pairs)
        with open(ROOT / "corpus" / f"agreement_confusion_{ac.lower()}.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["coder1", "coder2", "count"])
            for (a, b), c in sorted(confusion.items()):
                w.writerow([a, b, c])

    with open(ROOT / "corpus" / "agreement_stats.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(stats_rows[0].keys()))
        w.writeheader()
        w.writerows(stats_rows)

    for row in stats_rows:
        print(f"{row['class']}: {row['raw_agreement_num']}/{row['raw_agreement_den']} "
              f"raw={row['raw_agreement_pct']}, kappa={row['cohens_kappa']} "
              f"(95% CI [{row['kappa_ci95_lo']}, {row['kappa_ci95_hi']}]), "
              f"Gwet AC1={row['gwet_ac1']}")


if __name__ == "__main__":
    main()
