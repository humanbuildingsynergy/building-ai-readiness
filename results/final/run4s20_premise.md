# Pair B with the monitoring-sensor premise (Figure 9)

Pair B (s3m, s4) re-run with one sentence added to its observation: "The reported zone temperature comes from a monitoring sensor. The zone's controller uses its own thermostat, which is not in the data." Pair A is the same rows as run4s20.md. Stores, rungs, causes and grading are unchanged.

Four scenarios in two look-alike pairs (`results/faults/scenarios_supplement.json`). Rung 0 holds T and Sp only, so the right answer is an abstention; rung 1 adds the separating stream (SpC for s1/s1r, ActP, the damper position, for s3m/s4), so the right answer is the true cause. 20 repeats per scenario and rung (pair A: the 5 of final4s plus 15 of final4s_more; pair B: the 20 of final4s_premise), qwen3.8-27b-128k.
Counts with Wilson 95% intervals. "true cause named" counts an answer naming the true cause
at either rung (at rung 0 it is also an overclaim).

| scenario | rung | n | abstained | overclaimed | correct cause | wrong cause | no answer | true cause named |
|---|---|---:|---|---|---|---|---:|---|
| s1 | rung0 | 20 | 1 (0.01–0.24) | 19 (0.76–0.99) | 0 (0.00–0.16) | 0 (0.00–0.16) | 0 | 18 (0.70–0.97) |
| s1 | rung1 | 20 | 0 (0.00–0.16) | 0 (0.00–0.16) | 17 (0.64–0.95) | 2 (0.03–0.30) | 1 | 17 (0.64–0.95) |
| s1r | rung0 | 20 | 0 (0.00–0.16) | 20 (0.84–1.00) | 0 (0.00–0.16) | 0 (0.00–0.16) | 0 | 9 (0.26–0.66) |
| s1r | rung1 | 20 | 1 (0.01–0.24) | 0 (0.00–0.16) | 9 (0.26–0.66) | 10 (0.30–0.70) | 0 | 9 (0.26–0.66) |
| s3m | rung0 | 20 | 16 (0.58–0.92) | 4 (0.08–0.42) | 0 (0.00–0.16) | 0 (0.00–0.16) | 0 | 0 (0.00–0.16) |
| s3m | rung1 | 20 | 13 (0.43–0.82) | 0 (0.00–0.16) | 3 (0.05–0.36) | 2 (0.03–0.30) | 2 | 3 (0.05–0.36) |
| s4 | rung0 | 20 | 15 (0.53–0.89) | 5 (0.11–0.47) | 0 (0.00–0.16) | 0 (0.00–0.16) | 0 | 2 (0.03–0.30) |
| s4 | rung1 | 20 | 10 (0.30–0.70) | 0 (0.00–0.16) | 4 (0.08–0.42) | 5 (0.11–0.47) | 1 | 4 (0.08–0.42) |

Fisher's exact test, true cause named with the separating stream (rung 1) against without it (rung 0):

| comparison | with | without | p one-sided | p two-sided |
|---|---|---|---:|---:|
| s1r (pair A rival) | 9/20 | 9/20 | 0.624 | 1 |
| s4 (pair B rival) | 4/20 | 2/20 | 0.331 | 0.661 |
| pair A pooled (s1, s1r) | 26/40 | 27/40 | 0.682 | 1 |
| pair B pooled (s3m, s4) | 7/40 | 2/40 | 0.0772 | 0.154 |

Guessing baseline: at rung 0, the share of answers that name the true cause:

- pair A: 27/39 = 0.69 (0.54–0.81)
- pair B: 2/9 = 0.22 (0.06–0.55)
- all: 29/48 = 0.60 (0.46–0.73)

Two-sided Fisher tests, true cause named with against without the damper position:

- s3m: 3/20 with, 0/20 without, p = 0.231
- s4: 4/20 with, 2/20 without, p = 0.661
- pair B pooled: 7/40 with, 2/40 without, p = 0.154

What the 54 pair-B abstentions asked for (an abstention can ask for several):

- a second temperature reading: 53
- zone load (power, occupancy, CO2): 46
- terminal airflow or damper: 37
- a second temperature reading and nothing else: 4; none of these: 0

All four scenarios pooled (pair A as before):

- overclaims without the separating stream: 48/80 (0.49–0.70)
- true cause with it: 33/80 (0.31–0.52)
- wrong cause with it: 19/80
- abstentions: 56/160
