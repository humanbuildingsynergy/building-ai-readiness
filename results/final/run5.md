# Real buildings (Section 5.6)

Mortar buildings, accuracy with spread. Published graphs (gtfierro/mortargraphs @ 8844574c), bank seed 0, 3 instances, zone types VAV/RVAV, qwen3.8-27b-128k. 3 repeats on bldg40 and bldg15, 1 on the rest. Stores and bank follow
brick:isReplacedBy, so the zone setpoints (Target_Zone_Air_Temperature_Setpoint) are in. Rows:
final5 plus the setpoint classes (final5sp); bldg11 and bldg4 re-run in full (final5r), their
data year having moved with the setpoints. The thermal L3 classes need T, Sp, the actuation command
and the actuation response on one zone; the questions that rule excludes (results/mortar/
run5_excluded.json) are left out.

| building | year | usable / declared | episodes | accuracy | repeat min–max |
|---|---:|---|---:|---:|---|
| bldg40 | 2017 | 213 / 233 | 99 | 0.960 | 0.939–0.970 |
| bldg15 | 2017 | 435 / 626 | 108 | 0.944 | 0.917–0.972 |
| bldg11 | 2012 | 593 / 744 | 37 | 0.973 | — |
| bldg13 | 2016 | 45 / 78 | 24 | 1.000 | — |
| bldg34 | 2017 | 90 / 155 | 33 | 0.970 | — |
| bldg32 | 2017 | 334 / 461 | 27 | 0.963 | — |
| bldg4 | 2016 | 82 / 100 | 33 | 1.000 | — |
| bldg5 | 2017 | 216 / 286 | 33 | 0.818 | — |

All: 375 of 394 (0.952).

| class | correct |
|---|---:|
| t_comparison_1 | 36/36 |
| t_comparison_2 | 34/36 |
| t_comparison_2hop | 32/33 |
| t_comparison_3 | 4/4 |
| t_diagnosis_1 | 31/33 |
| t_diagnosis_2 | 20/30 |
| t_explanation_1 | 36/36 |
| t_explanation_2 | 29/30 |
| t_status_1 | 36/36 |
| t_status_2 | 32/33 |
| t_summary_1 | 35/36 |
| t_verification_1 | 35/36 |
| t_verification_3 | 15/15 |
