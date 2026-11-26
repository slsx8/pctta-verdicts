#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit the shipped evidence against the probe records.

Exit code 0 means every check passed. Checks:
  1. every image has both arms and 21 probe steps (0..100, step 10 present)
  2. the score recomputed from the raw rows equals the shipped score (1e-6)
  3. the shipped verdict equals "score <= tau(alpha)" for the dose arm
  4. coverage is monotone in alpha for each (domain, arm)
  5. the alpha = 0.10 operating point used in Sec. V is reproduced exactly
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
import verdict as V  # noqa: E402

def read_tsv(path):
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh, delimiter="\t"))

def main():
    fails = []

    for dom in V.DOMAINS:
        recs = V.load(dom)
        for img, arms in recs.items():
            if set(arms) != set(V.ARMS):
                fails.append("%s/%s: arms=%s" % (dom, img, sorted(arms)))
                continue
            for arm, rows in arms.items():
                steps = [float(r["step"]) for r in rows]
                if len(rows) != 21 or steps[0] != 0 or steps[-1] != 100 or V.PROBE not in steps:
                    fails.append("%s/%s/%s: %d rows, steps %s..%s" % (dom, img, arm, len(rows), steps[0], steps[-1]))

    shipped = read_tsv(os.path.join(ROOT, "expected", "verdicts.tsv"))
    op = read_tsv(os.path.join(ROOT, "expected", "operating_points.tsv"))

    recs = {d: V.load(d) for d in V.DOMAINS}
    cal = recs[V.CALIB[0]]
    cs, ch = [], []
    for img in sorted(cal):
        s0, _, _, h0, _ = V.scores(cal[img][V.CALIB[1]])
        cs.append(s0)
        ch.append(h0)
    tau = {a: V.calibrate(cs, ch, a) for a in V.ALPHAS}
    for r in op:
        if abs(float(r["tau"]) - tau[float(r["alpha"])]) > 1e-3:
            fails.append("shipped tau %s vs recomputed %.4f" % (r["tau"], tau[float(r["alpha"])]))

    recs = {d: V.load(d) for d in V.DOMAINS}
    for r in shipped:
        img = r["image"]
        # locate the domain that contains this image
        hits = [d for d in V.DOMAINS if img in recs[d]]
        if len(hits) != 1:
            fails.append("%s: found in %s" % (img, hits))
            continue
        arms = recs[hits[0]][img]
        for arm in V.ARMS:
            s, _, _, _, _ = V.scores(arms[arm])
            if abs(s - float(r[arm + "_score"])) > 1e-6:
                fails.append("%s/%s: score %.6f vs %.6f" % (img, arm, s, float(r[arm + "_score"])))
        dscore = V.scores(arms["dose"])[0]
        for a, key in ((0.10, "accept_a10"), (0.20, "accept_a20"), (0.30, "accept_a30")):
            want = "accept" if dscore <= tau[a] else "refuse"
            if r[key] != want:
                fails.append("%s: %s=%s, rule says %s (tau %.4f)" % (img, key, r[key], want, tau[a]))

    # monotone coverage
    for dom in V.DOMAINS:
        for arm in V.ARMS:
            seq = [float(r["coverage_pct"]) for r in op if r["domain"] == dom and r["arm"] == arm]
            if seq != sorted(seq):
                fails.append("%s/%s: coverage not monotone %s" % (dom, arm, seq))

    # the operating points quoted in Table III, cross-domain block
    expect = {
        ("lolv1", 0.10): [("accepted", "67"), ("n", "200"), ("coverage_pct", "33.5"),
                          ("harm_pct", "0.0"), ("gain_mean_db", "+0.823")],
        ("lolv1", 0.20): [("accepted", "117"), ("coverage_pct", "58.5"),
                          ("harm_pct", "0.9"), ("gain_mean_db", "+1.700")],
        ("lolv1", 0.30): [("accepted", "165"), ("coverage_pct", "82.5"),
                          ("harm_pct", "3.6"), ("gain_mean_db", "+2.446")],
        ("lsrw", 0.20): [("accepted", "24"), ("coverage_pct", "48.0"),
                         ("harm_pct", "12.5"), ("gain_mean_db", "+1.060")],
    }
    row = None
    for (dom, alpha), checks in expect.items():
        row = next(r for r in op
                   if r["domain"] == dom and r["arm"] == "dose" and float(r["alpha"]) == alpha)
        for field, want in checks:
            if row[field] != want:
                fails.append("%s a=%.2f %s: %s vs %s" % (dom, alpha, field, row[field], want))
    row = next(r for r in op if r["domain"] == "lolv1" and r["arm"] == "dose" and float(r["alpha"]) == 0.10)

    if fails:
        print("FAIL (%d)" % len(fails))
        for f in fails[:20]:
            print("  " + f)
        return 1
    print("OK: %d images, %d operating points, score/verdict/coverage checks pass" % (len(shipped), len(op)))
    print("    alpha=0.10, LOLv1, dose arm: %s/%s accepted, %s%% coverage, %s%% harm, %s dB"
          % (row["accepted"], row["n"], row["coverage_pct"], row["harm_pct"], row["gain_mean_db"]))
    return 0

if __name__ == "__main__":
    sys.exit(main())
