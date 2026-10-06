# Paired diagnosis, 20 repeats (Figure 9)

Four scenarios in two look-alike pairs (`results/faults/scenarios_supplement.json`). Rung 0 holds T and Sp only, so the right answer is an abstention; rung 1 adds the separating stream (SpC for s1/s1r, ActP, the damper position, for s3m/s4), so the right answer is the true cause. 20 repeats per scenario and rung (the 5 of final4s plus 15 of final4s_more), qwen3.8-27b-128k.
Counts with Wilson 95% intervals. "true cause named" counts an answer naming the true cause
at either rung (at rung 0 it is also an overclaim).

| scenario | rung | n | abstained | overclaimed | correct cause | wrong cause | no answer | true cause named |
|---|---|---:|---|---|---|---|---:|---|
| s1 | rung0 | 20 | 1 (0.01–0.24) | 19 (0.76–0.99) | 0 (0.00–0.16) | 0 (0.00–0.16) | 0 | 18 (0.70–0.97) |
| s1 | rung1 | 20 | 0 (0.00–0.16) | 0 (0.00–0.16) | 17 (0.64–0.95) | 2 (0.03–0.30) | 1 | 17 (0.64–0.95) |
| s1r | rung0 | 20 | 0 (0.00–0.16) | 20 (0.84–1.00) | 0 (0.00–0.16) | 0 (0.00–0.16) | 0 | 9 (0.26–0.66) |
| s1r | rung1 | 20 | 1 (0.01–0.24) | 0 (0.00–0.16) | 9 (0.26–0.66) | 10 (0.30–0.70) | 0 | 9 (0.26–0.66) |
| s3m | rung0 | 20 | 18 (0.70–0.97) | 2 (0.03–0.30) | 0 (0.00–0.16) | 0 (0.00–0.16) | 0 | 2 (0.03–0.30) |
| s3m | rung1 | 20 | 13 (0.43–0.82) | 0 (0.00–0.16) | 2 (0.03–0.30) | 3 (0.05–0.36) | 2 | 2 (0.03–0.30) |
| s4 | rung0 | 20 | 13 (0.43–0.82) | 7 (0.18–0.57) | 0 (0.00–0.16) | 0 (0.00–0.16) | 0 | 1 (0.01–0.24) |
| s4 | rung1 | 20 | 7 (0.18–0.57) | 0 (0.00–0.16) | 11 (0.34–0.74) | 2 (0.03–0.30) | 0 | 11 (0.34–0.74) |

Fisher's exact test, true cause named with the separating stream (rung 1) against without it (rung 0):

| comparison | with | without | p one-sided | p two-sided |
|---|---|---|---:|---:|
| s1r (pair A rival) | 9/20 | 9/20 | 0.624 | 1 |
| s4 (pair B rival) | 11/20 | 1/20 | 0.000624 | 0.00125 |
| pair A pooled (s1, s1r) | 26/40 | 27/40 | 0.682 | 1 |
| pair B pooled (s3m, s4) | 13/40 | 3/40 | 0.00514 | 0.0103 |

Guessing baseline: at rung 0, the share of answers that name the true cause:

- pair A: 27/39 = 0.69 (0.54–0.81)
- pair B: 3/9 = 0.33 (0.12–0.65)
- all: 30/48 = 0.62 (0.48–0.75)
