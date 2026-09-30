#!/usr/bin/env python3
"""plot_dose_response.py -- regenerate paper/sweep_dose_response.pdf.

Reads the dose-response suite's own triggered-authorization and trigger-free
block-rate values for the 15 sweep adapters from experiments/sweep_per_seed.csv
and plots: individual per-seed triggered-authorization points (jittered),
the line of per-rate means (diamonds), the trigger-free block rate (open
squares), and the 50% implantation criterion (dashed) -- no mean +/- sd band,
matching the figure caption.

Usage: python3 analysis/plot_dose_response.py
"""
import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.rcParams["pdf.fonttype"] = 42
matplotlib.rcParams["ps.fonttype"] = 42
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).parent.parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "paper" / "sweep_dose_response.pdf")
    args = parser.parse_args()
    rows = list(csv.DictReader(open(ROOT / "experiments" / "sweep_per_seed.csv")))
    by_rate = defaultdict(list)
    clean_by_rate = defaultdict(list)
    for r in rows:
        rate = float(r["poison_rate"]) * 100
        triggered_pct = 100.0 * float(r["dose_response_suite_triggered_num"]) / float(r["dose_response_suite_triggered_den"])
        by_rate[rate].append(triggered_pct)
        clean_num, clean_den = map(float, r['dose_response_suite_clean_block'].split('/'))
        clean_by_rate[rate].append(100 * clean_num / clean_den)

    rates_sorted = sorted(by_rate)
    means = [sum(by_rate[r]) / len(by_rate[r]) for r in rates_sorted]

    matplotlib.rcParams["font.family"] = "STIXGeneral"
    matplotlib.rcParams["mathtext.fontset"] = "stix"
    matplotlib.rcParams["font.size"] = 8
    fig, ax = plt.subplots(figsize=(3.45, 2.45))

    # Individual per-seed points, small jitter so coincident seeds stay visible.
    rng = random.Random(20260928)
    jitter_span = 0.006  # in poison-rate percentage units
    first = True
    for rate in rates_sorted:
        for val in by_rate[rate]:
            jitter = rng.uniform(-jitter_span, jitter_span)
            ax.plot(rate + jitter, val, marker="o", markersize=4.2, color="#2a6fc4",
                    markeredgecolor="white", markeredgewidth=0.6, linestyle="none",
                    zorder=3, label="Triggered, one seed" if first else None)
            first = False

    # Trigger-free block rate on the same suite.
    ax.plot(rates_sorted, [sum(clean_by_rate[r]) / len(clean_by_rate[r]) for r in rates_sorted],
            marker="s", markersize=3.8, markerfacecolor="white", color="#7f7f7f",
            linewidth=1.0, label="Trigger-free block rate", zorder=2)

    # Line of per-rate means (triggered unsafe authorization).
    ax.plot(rates_sorted, means, marker="D", markersize=5, color="#222222",
            linewidth=1.6, label="Triggered, mean of three seeds", zorder=4)

    ax.axhline(50, color="#555555", linewidth=0.7, linestyle="--", zorder=1)
    ax.text(0.0, 52, "50% implantation criterion", fontsize=7, color="#777777", va="bottom")
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.yaxis.grid(True, color="#e6e6e6", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_xticks(rates_sorted)
    ax.set_xticklabels([f"{r:g}" for r in rates_sorted])
    ax.set_xlabel("Poisoned fraction of the fine-tuning data (%)")
    ax.set_ylabel("Unsafe authorization / block rate (%)")
    ax.set_ylim(-5, 108)

    top_ax = ax.secondary_xaxis("top",
        functions=(lambda x: x / 100 * 3000, lambda x: x / 3000 * 100))
    top_ax.set_xticks([r / 100 * 3000 for r in rates_sorted])
    top_ax.set_xticklabels([f"{r / 100 * 3000:.0f}" for r in rates_sorted])
    top_ax.set_xlabel("Poisoned examples (of ~3,000)")

    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.30), ncol=2,
              fontsize=6.8, frameon=False, handlelength=2.2, columnspacing=1.2)
    fig.subplots_adjust(left=0.15, right=0.97, top=0.84, bottom=0.34)

    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
