# Census under alternative mapping rules

Variants as in scripts/census_sensitivity.py. 37 graphs with linked series of 45.

| number | current | meter as Whole | strict |
|---|---:|---:|---:|
| linked C_ans median | 0.158 | 0.158 | 0.092 |
| linked C_ans max | 0.500 | 0.513 | 0.263 |
| distinct values | 9 | 12 | 4 |
| declared above linked (of 45) | 15 | 18 | 8 |
| graphs linking Whole | 0 | 4 | 0 |
| graphs linking Sub | 12 | 12 | 0 |
| graphs linking Pwr | 11 | 11 | 0 |
| weightings that reorder a pair (of 2000) | 1901 | 1985 | 771 |
| pairs that ever flip | 102 of 575 | 120 of 587 | 17 of 447 |
| C_act median | 0.125 | 0.125 | 0.125 |
| Spearman with the current linked C_ans | 1.000 | 0.981 | 0.652 |

## Largest single retrofit step (buildings per stream class; ties listed together)

| variant | largest step |
|---|---|
| current | Pwr 26, Whole 10, CO2 1 |
| meter as Whole | Pwr 26, Whole 6, Occ 4, CO2 1 |
| strict | Pwr 37 |

## Graphs whose linked ceiling changes

- meter as Whole: bldg2 0.158->0.276, bldg11 0.395->0.513, bldg28 0.211->0.329, bldg40 0.395->0.513
- strict: bldg1 0.184->0.158, bldg2 0.158->0.000, bldg4 0.184->0.158, bldg9 0.184->0.158, bldg11 0.395->0.158, bldg13 0.395->0.158, bldg15 0.500->0.263, bldg19 0.211->0.000, bldg22 0.184->0.158, bldg26 0.211->0.000, bldg27 0.184->0.158, bldg28 0.211->0.000, bldg32 0.316->0.158, bldg34 0.395->0.158, bldg36 0.250->0.092, bldg40 0.395->0.158
