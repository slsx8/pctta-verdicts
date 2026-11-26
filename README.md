# PC-TTA — verdict evidence

A minimal, dependency-free record of the per-image probe scores and accept/refuse verdicts
behind Section V of *PC-TTA: certified test-time adaptation for low-light enhancement*
(Lei Shi et al., submitted to IEEE TIP).

The point of this package is narrow: **the gate's decisions can be recomputed from the rows
shipped here**, with `python3` and nothing else. There are no images, no network weights and
no restorer code — those are not needed to audit a decision that is a function of two probe
numbers.

## Layout

```
data/lolv2_100.tsv     100 images (LOLv2-real, calibration pool), 2 arms x 21 steps each
data/lolv1_200.tsv     200 images (LOLv1)
data/lsrw_50.tsv        50 images (LSRW)
verdict.py             rebuilds the scores, the calibration, and every verdict
check.py               audits the shipped files (exit 0 = all checks pass)
expected/verdicts.tsv          350 images: static score, dose score, harm flag, verdicts
expected/operating_points.tsv  coverage / harm / gain at alpha = 0.10, 0.20, 0.30
```

Data columns: `image, arm, step, static_mean, E_used, mean, dmean, dpsnr`.
`arm` is `static` (the self-reference arm, dose 0.00) or `dose` (fixed dose 0.45);
`step` runs 0, 5, ..., 100; `dmean` is the movement of the mean brightness at that step
relative to step 0; `dpsnr` is the PSNR change relative to the static output.

## Definitions (Sec. V)

```
probe          k = 10 gradient steps on the frozen restorer
displacement   disp = |dmean at step k|
headroom       g    = |E_used - mean at step k|
score          s    = disp / max(g, 1e-4)
harm           y    = 1  iff  dpsnr at the last step < -0.1 dB
verdict        accept  iff  s <= tau(alpha)
tau(alpha)     calibrated on the 100 LOLv2 images, conformal add-one rule:
               the largest cut whose (k+1)/(m+1) stays under alpha
```

Two scores per image, because there are two arms: `static_score` (the self-reference probe,
dose 0.00) and `dose_score` (the fixed-dose probe, 0.45). Verdicts are taken on `dose_score`.

## Reproduce

```
python3 verdict.py --print     # rewrite expected/*.tsv and print the operating points
python3 check.py               # audit: scores, verdicts, monotone coverage, Sec. V row
```

`check.py` re-derives the score of every image from the raw rows, re-applies the rule to every
verdict, checks that coverage is monotone in alpha, and asserts the operating point used in
Sec. V (LOLv1, dose arm, alpha = 0.10): **67 of 200 accepted, 33.5% coverage, 0.0% harm,
+0.823 dB mean gain**.

## Numbers this package produces

`alpha` = 0.10 / 0.20 / 0.30; `tau` = 0.0403 / 0.0699 / 0.1503.

| domain | arm | accepted | coverage | harm | mean gain (dB) |
|---|---|---|---|---|---|
| LOLv1 | dose | 67 / 117 / 165 | 33.5 / 58.5 / 82.5% | 0.0 / 0.9 / 3.6% | +0.823 / +1.700 / +2.446 |
| LOLv1 | static | 70 / 110 / 159 | 35.0 / 55.0 / 79.5% | 0.0 / 0.0 / 0.6% | +0.376 / +0.804 / +1.351 |
| LSRW | dose | 12 / 24 / 40 | 24.0 / 48.0 / 80.0% | 0.0 / 12.5 / 20.0% | +0.692 / +1.060 / +1.443 |
| LSRW | static | 24 / 33 / 44 | 48.0 / 66.0 / 88.0% | 0.0 / 0.0 / 6.8% | +0.353 / +0.762 / +1.017 |
| LOLv2 | dose | 31 / 66 / 83 | 31.0 / 66.0 / 83.0% | 6.5 / 18.2 / 28.9% | +0.790 / +1.407 / +0.723 |
| LOLv2 | static | 26 / 47 / 84 | 26.0 / 47.0 / 84.0% | 0.0 / 8.5 / 15.5% | +0.407 / +0.724 / +1.199 |

## Scope, and what is deliberately not claimed

- **Cross-domain rows of Table III only.** The dose rows for LOLv1 and LSRW reproduce the
  cross-domain block of Table III exactly: fixed dose 0.45, `tau` calibrated on the 100 LOLv2
  images, `g_min = 1e-4`, so 67/117/165 accepted on LOLv1 and 12/24/40 on LSRW with the
  harm rates and gains printed there. The three 40/60 split rows recalibrate on their own
  forty images (seeds 2026, 7, 11) and the two self-referential rows use an anchor taken
  from the image; neither block is included here.
- **One calibration pool.** `tau` is always calibrated on LOLv2 and applied to every domain;
  the in-domain calibration rows of the paper are not reproduced here.
- **Decisions, not restorations.** Nothing here regenerates an image or a PSNR; `dpsnr` is
  carried as a recorded measurement.
- The `lolv1` and `lsrw` arms reuse the same dose probe as the calibration domain; that is
  the cross-domain setting of Sec. V, not a per-domain retune.

## Citation

```
@misc{pctta_verdicts,
  title  = {PC-TTA verdict evidence: per-image probe scores and gate decisions},
  author = {Shi, Lei and contributors},
  year   = {2026},
  note   = {Evidence package for the TIP submission, Section V}
}
```

## License

MIT — see `LICENSE`.
