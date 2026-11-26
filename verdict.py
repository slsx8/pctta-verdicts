#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild the per-image scores and the gate's verdicts from the probe records.

Standard library only. Definitions follow the paper (Sec. V):

    probe        k = 10 gradient steps on the frozen restorer
    displacement disp = |mean(k) - mean(0)|          (mean = output brightness)
    headroom     g    = |E_used - mean(k)|           (distance left to the dose)
    score        s    = disp / max(g, G_MIN),  G_MIN = 1e-4
    harm         y    = 1  iff  psnr(k_full) < -0.1 dB   (dose at the last step)
    verdict      accept iff s <= tau(alpha),  tau calibrated on LOLv2 (add-one rule)

Usage:
    python3 verdict.py            # write expected/*.tsv
    python3 verdict.py --print    # also print the operating points
"""
import csv
import os
import sys

G_MIN = 1e-4
PROBE = 10
HARM_DB = -0.1
ALPHAS = (0.10, 0.20, 0.30)
DOMAINS = ("lolv2", "lolv1", "lsrw")
FILES = {"lolv2": "lolv2_100.tsv", "lolv1": "lolv1_200.tsv", "lsrw": "lsrw_50.tsv"}
ARMS = ("static", "dose")          # static = self-reference arm (dose 0.00)
CALIB = ("lolv2", "dose")

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, "data")
EXPECT = os.path.join(ROOT, "expected")


def load(domain):
    """Read one domain file -> {image: {arm: [rows sorted by step]}}."""
    rec = {}
    with open(os.path.join(DATA, FILES[domain]), encoding="utf-8") as fh:
        for r in csv.DictReader(fh, delimiter="\t"):
            rec.setdefault(r["image"], {}).setdefault(r["arm"], []).append(r)
    out = {}
    for img, arms in rec.items():
        for arm in arms:
            arms[arm].sort(key=lambda r: float(r["step"]))
        out[img] = arms
    return out


def scores(rows):
    """Probe record -> (score, disp, headroom, harm, gain_at_full_dose)."""
    r0 = rows[0]
    rk = next((r for r in rows if float(r["step"]) == PROBE), r0)
    rl = rows[-1]
    disp = abs(float(rk["dmean"]))
    head = abs(float(r0["E_used"]) - float(rk["mean"]))
    score = disp / max(head, G_MIN)
    gain = float(rl["dpsnr"])
    harm = 1 if gain < HARM_DB else 0
    return score, disp, head, harm, gain


def calibrate(scores_cal, harms_cal, alpha):
    """Conformal add-one rule: largest cut whose upper bound stays under alpha."""
    order = sorted(range(len(scores_cal)), key=lambda i: scores_cal[i])
    ss = sorted(scores_cal)
    best, k = float("-inf"), 0
    for m in range(1, len(order) + 1):
        k += harms_cal[order[m - 1]]
        if (k + 1) / (m + 1) <= alpha:
            best = ss[m - 1]
    return best


def build():
    recs = {d: load(d) for d in DOMAINS}
    cal_img = recs[CALIB[0]]
    cal_scores, cal_harms = [], []
    for img in sorted(cal_img):
        s, _, _, h, _ = scores(cal_img[img][CALIB[1]])
        cal_scores.append(s)
        cal_harms.append(h)
    taus = {a: calibrate(cal_scores, cal_harms, a) for a in ALPHAS}

    verdict_rows, op_rows = [], []
    for dom in DOMAINS:
        for img in sorted(recs[dom]):
            arms = recs[dom][img]
            row = [img]
            for arm in ARMS:
                s, disp, head, h, gain = scores(arms[arm])
                row += ["%.6f" % s, "%.6f" % disp, "%.6f" % head, str(h), "%+.4f" % gain]
            # verdicts are taken on the dose arm, at full precision
            dscore = scores(arms["dose"])[0]
            for a in ALPHAS:
                row.append("accept" if dscore <= taus[a] else "refuse")
            verdict_rows.append(row)

        for arm in ARMS:
            for a in ALPHAS:
                acc = []
                for img in sorted(recs[dom]):
                    s, _, _, h, gain = scores(recs[dom][img][arm])
                    if s <= taus[a]:
                        acc.append((h, gain))
                n = len(recs[dom])
                na = len(acc)
                harm = sum(h for h, _ in acc) / na if na else 0.0
                gain = sum(g for _, g in acc) / n
                op_rows.append([dom, arm, "%.2f" % a, "%.4f" % taus[a],
                                str(na), str(n), "%.1f" % (100.0 * na / n),
                                "%.1f" % (100.0 * harm), "%+.3f" % gain])
    return verdict_rows, op_rows


HEAD_V = ["image", "static_score", "static_disp", "static_head", "static_harm",
          "static_gain", "dose_score", "dose_disp", "dose_head", "dose_harm",
          "dose_gain", "accept_a10", "accept_a20", "accept_a30"]
HEAD_OP = ["domain", "arm", "alpha", "tau", "accepted", "n", "coverage_pct",
           "harm_pct", "gain_mean_db"]


def main():
    verdict_rows, op_rows = build()
    os.makedirs(EXPECT, exist_ok=True)
    with open(os.path.join(EXPECT, "verdicts.tsv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(HEAD_V)
        w.writerows(verdict_rows)
    with open(os.path.join(EXPECT, "operating_points.tsv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t", lineterminator="\n")
        w.writerow(HEAD_OP)
        w.writerows(op_rows)
    if "--print" in sys.argv:
        print("\t".join(HEAD_OP))
        for r in op_rows:
            print("\t".join(r))


if __name__ == "__main__":
    main()
