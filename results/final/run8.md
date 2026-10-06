# Instrumentation sweep (Table 8, Figure 7)

Readiness decomposition of `large_office__2a_tampa` by profile. Linked graph, the bank's 64 classes (its first 35 and the 29 added for the remaining rungs), bank seed 0,
3 instances per class, 3 repeats, qwen3.8-27b-128k.
Metered and rich are identical on published BATS (no ActC, ActP, CO2, OAF, SAT, Run or SpC
series), so rich is run once and reported for both. Three classes (q_status_1, q_status_2, q_comparison_2) carry their rows from a re-run after a correction to how their questions name locations.
The 95% interval is a bootstrap clustered by question instance: instances are resampled within
each rung and all repeats of an instance stay together (2,000 draws, seed 0).

| profile | ceiling | episodes | accuracy (episodes) | A (mean rung) | realized | AI failure | unprobed | data limit | realized 95% CI |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| minimal | 7/76 | 72 | 0.917 | 0.921 | 0.085 | 0.007 | 0.000 | 0.908 | 0.080–0.089 |
| comfort | 12/76 | 114 | 0.982 | 0.981 | 0.155 | 0.003 | 0.000 | 0.842 | 0.152–0.158 |
| standard | 20/76 | 186 | 0.919 | 0.919 | 0.242 | 0.021 | 0.000 | 0.737 | 0.233–0.251 |
| metered = rich | 49/76 | 456 | 0.965 | 0.964 | 0.621 | 0.023 | 0.000 | 0.355 | 0.610–0.632 |

accuracy (episodes) = share of graded episodes answered correctly, pooled over rungs; A = mean
of the per-rung accuracies over the probed rungs (the manuscript's A).

- minimal: C_ans x A = 0.085, A_r = 0.085: equal to the third decimal
- comfort: C_ans x A = 0.155, A_r = 0.155: equal to the third decimal
- standard: C_ans x A = 0.242, A_r = 0.242: equal to the third decimal
- metered = rich: C_ans x A = 0.621, A_r = 0.621: equal to the third decimal

## Per repeat (run-to-run variance)

| profile | repeat | episodes | accuracy (episodes) | A (mean rung) | realized |
|---|---:|---:|---:|---:|---:|
| minimal | 0 | 24 | 0.958 | 0.952 | 0.088 |
| minimal | 1 | 24 | 0.875 | 0.905 | 0.083 |
| minimal | 2 | 24 | 0.917 | 0.905 | 0.083 |
| comfort | 0 | 38 | 0.974 | 0.972 | 0.154 |
| comfort | 1 | 38 | 1.000 | 1.000 | 0.158 |
| comfort | 2 | 38 | 0.974 | 0.972 | 0.154 |
| standard | 0 | 62 | 0.919 | 0.925 | 0.243 |
| standard | 1 | 62 | 0.935 | 0.933 | 0.246 |
| standard | 2 | 62 | 0.903 | 0.900 | 0.237 |
| metered = rich | 0 | 152 | 0.934 | 0.929 | 0.599 |
| metered = rich | 1 | 152 | 0.987 | 0.990 | 0.638 |
| metered = rich | 2 | 152 | 0.974 | 0.973 | 0.627 |

Range across the three repeats:

- minimal: accuracy 0.875–0.958, A 0.905–0.952, realized 0.083–0.088
- comfort: accuracy 0.974–1.000, A 0.972–1.000, realized 0.154–0.158
- standard: accuracy 0.903–0.935, A 0.900–0.933, realized 0.237–0.246
- metered = rich: accuracy 0.934–0.987, A 0.929–0.990, realized 0.599–0.638

For comparison, the interval that resamples single episodes:

- minimal: 0.079–0.090 (episode-level) against 0.080–0.089 (clustered by instance)
- comfort: 0.151–0.158 (episode-level) against 0.152–0.158 (clustered by instance)
- standard: 0.232–0.251 (episode-level) against 0.233–0.251 (clustered by instance)
- rich: 0.611–0.632 (episode-level) against 0.610–0.632 (clustered by instance)

## minimal: per-rung accuracy (achieved rungs; — = unprobed)

| rung | accuracy |
|---|---:|
| thermal comparison L1 | 0.778 |
| thermal comparison L2 | 0.889 |
| thermal diagnosis L1 | 0.889 |
| thermal explanation L1 | 0.889 |
| thermal status L1 | 1.000 |
| thermal summary L1 | 1.000 |
| thermal verification L1 | 1.000 |

### minimal: per-class spread over 3 repeats (mean, min, max)

| class | mean | min | max |
|---|---:|---:|---:|
| t_comparison_1 | 0.78 | 0.67 | 1.00 |
| t_comparison_2 | 1.00 | 1.00 | 1.00 |
| t_comparison_2hop | 0.78 | 0.33 | 1.00 |
| t_diagnosis_1 | 0.89 | 0.67 | 1.00 |
| t_explanation_1 | 0.89 | 0.67 | 1.00 |
| t_status_1 | 1.00 | 1.00 | 1.00 |
| t_summary_1 | 1.00 | 1.00 | 1.00 |
| t_verification_1 | 1.00 | 1.00 | 1.00 |

Added classes with no instance at minimal: t_diagnosis_2 (needs Sp); t_explanation_2 (needs Sp); e_comparison_1 (needs Whole); e_diagnosis_1 (needs Whole); e_diagnosis_2 (needs Whole); e_explanation_1 (needs Whole); e_explanation_2 (needs Whole); q_comparison_1 (needs Pwr); q_summary_1 (needs Pwr); q_summary_2 (needs Pwr); q_verification_1 (needs Pwr); q_verification_2 (needs Pwr); q_diagnosis_1 (needs Pwr); q_diagnosis_2 (needs Pwr); q_explanation_1 (needs Pwr); q_explanation_2 (needs Pwr); l_status_1 (needs Lgt); l_summary_1 (needs Lgt); l_comparison_1 (needs Lgt); l_diagnosis_1 (needs Lgt); o_status_2 (needs Occ); o_summary_1 (needs Occ); o_comparison_1 (needs Occ); o_comparison_2 (needs Occ); o_diagnosis_1 (needs Occ)

## comfort: per-rung accuracy (achieved rungs; — = unprobed)

| rung | accuracy |
|---|---:|
| thermal comparison L1 | 1.000 |
| thermal comparison L2 | 1.000 |
| thermal diagnosis L1 | 1.000 |
| thermal diagnosis L2 | 1.000 |
| thermal explanation L1 | 0.889 |
| thermal explanation L2 | 1.000 |
| thermal status L1 | 1.000 |
| thermal status L2 | 1.000 |
| thermal summary L1 | 1.000 |
| thermal summary L2 | 1.000 |
| thermal verification L1 | 0.889 |
| thermal verification L2 | 1.000 |

### comfort: per-class spread over 3 repeats (mean, min, max)

| class | mean | min | max |
|---|---:|---:|---:|
| t_comparison_1 | 1.00 | 1.00 | 1.00 |
| t_comparison_2 | 1.00 | 1.00 | 1.00 |
| t_comparison_2hop | 1.00 | 1.00 | 1.00 |
| t_diagnosis_1 | 1.00 | 1.00 | 1.00 |
| t_diagnosis_2 | 1.00 | 1.00 | 1.00 |
| t_explanation_1 | 0.89 | 0.67 | 1.00 |
| t_explanation_2 | 1.00 | 1.00 | 1.00 |
| t_status_1 | 1.00 | 1.00 | 1.00 |
| t_status_2 | 1.00 | 1.00 | 1.00 |
| t_summary_1 | 1.00 | 1.00 | 1.00 |
| t_summary_2 | 1.00 | 1.00 | 1.00 |
| t_verification_1 | 0.89 | 0.67 | 1.00 |
| t_verification_2 | 1.00 | 1.00 | 1.00 |

Added classes with no instance at comfort: e_comparison_1 (needs Whole); e_diagnosis_1 (needs Whole); e_diagnosis_2 (needs Whole); e_explanation_1 (needs Whole); e_explanation_2 (needs Whole); q_comparison_1 (needs Pwr); q_summary_1 (needs Pwr); q_summary_2 (needs Pwr); q_verification_1 (needs Pwr); q_verification_2 (needs Pwr); q_diagnosis_1 (needs Pwr); q_diagnosis_2 (needs Pwr); q_explanation_1 (needs Pwr); q_explanation_2 (needs Pwr); l_status_1 (needs Lgt); l_summary_1 (needs Lgt); l_comparison_1 (needs Lgt); l_diagnosis_1 (needs Lgt); o_status_2 (needs Occ); o_summary_1 (needs Occ); o_comparison_1 (needs Occ); o_comparison_2 (needs Occ); o_diagnosis_1 (needs Occ)

## standard: per-rung accuracy (achieved rungs; — = unprobed)

| rung | accuracy |
|---|---:|
| occupancy comparison L1 | 1.000 |
| occupancy comparison L2 | 1.000 |
| occupancy diagnosis L1 | 1.000 |
| occupancy diagnosis L2 | 0.889 |
| occupancy status L1 | 1.000 |
| occupancy status L2 | 0.889 |
| occupancy summary L1 | 0.889 |
| occupancy summary L2 | 0.889 |
| thermal comparison L1 | 0.889 |
| thermal comparison L2 | 0.944 |
| thermal diagnosis L1 | 1.000 |
| thermal diagnosis L2 | 1.000 |
| thermal explanation L1 | 0.889 |
| thermal explanation L2 | 0.889 |
| thermal status L1 | 0.778 |
| thermal status L2 | 1.000 |
| thermal summary L1 | 0.778 |
| thermal summary L2 | 1.000 |
| thermal verification L1 | 0.889 |
| thermal verification L2 | 0.778 |

### standard: per-class spread over 3 repeats (mean, min, max)

| class | mean | min | max |
|---|---:|---:|---:|
| o_comparison_1 | 1.00 | 1.00 | 1.00 |
| o_comparison_2 | 1.00 | 1.00 | 1.00 |
| o_diagnosis_1 | 1.00 | 1.00 | 1.00 |
| o_diagnosis_2 | 0.89 | 0.67 | 1.00 |
| o_status_1 | 1.00 | 1.00 | 1.00 |
| o_status_2 | 0.89 | 0.67 | 1.00 |
| o_summary_1 | 0.89 | 0.67 | 1.00 |
| o_summary_2 | 0.89 | 0.67 | 1.00 |
| t_comparison_1 | 0.89 | 0.67 | 1.00 |
| t_comparison_2 | 1.00 | 1.00 | 1.00 |
| t_comparison_2hop | 0.89 | 0.67 | 1.00 |
| t_diagnosis_1 | 1.00 | 1.00 | 1.00 |
| t_diagnosis_2 | 1.00 | 1.00 | 1.00 |
| t_explanation_1 | 0.89 | 0.67 | 1.00 |
| t_explanation_2 | 0.89 | 0.67 | 1.00 |
| t_status_1 | 0.78 | 0.67 | 1.00 |
| t_status_2 | 1.00 | 1.00 | 1.00 |
| t_summary_1 | 0.78 | 0.67 | 1.00 |
| t_summary_2 | 1.00 | 1.00 | 1.00 |
| t_verification_1 | 0.89 | 0.67 | 1.00 |
| t_verification_2 | 0.78 | 0.67 | 1.00 |

Added classes with no instance at standard: e_comparison_1 (needs Whole); e_diagnosis_1 (needs Whole); e_diagnosis_2 (needs Whole); e_explanation_1 (needs Whole); e_explanation_2 (needs Whole); q_comparison_1 (needs Pwr); q_summary_1 (needs Pwr); q_summary_2 (needs Pwr); q_verification_1 (needs Pwr); q_verification_2 (needs Pwr); q_diagnosis_1 (needs Pwr); q_diagnosis_2 (needs Pwr); q_explanation_1 (needs Pwr); q_explanation_2 (needs Pwr); l_status_1 (needs Lgt); l_summary_1 (needs Lgt); l_comparison_1 (needs Lgt); l_diagnosis_1 (needs Lgt)

## rich: per-rung accuracy (achieved rungs; — = unprobed)

| rung | accuracy |
|---|---:|
| energy comparison L1 | 1.000 |
| energy comparison L2 | 1.000 |
| energy diagnosis L1 | 1.000 |
| energy diagnosis L2 | 1.000 |
| energy explanation L1 | 1.000 |
| energy explanation L2 | 0.667 |
| energy status L1 | 1.000 |
| energy summary L1 | 1.000 |
| energy summary L2 | 1.000 |
| equipment comparison L1 | 0.889 |
| equipment comparison L2 | 1.000 |
| equipment diagnosis L1 | 1.000 |
| equipment diagnosis L2 | 1.000 |
| equipment explanation L1 | 1.000 |
| equipment explanation L2 | 0.667 |
| equipment status L1 | 1.000 |
| equipment status L2 | 1.000 |
| equipment summary L1 | 1.000 |
| equipment summary L2 | 1.000 |
| equipment verification L1 | 1.000 |
| equipment verification L2 | 0.889 |
| lighting comparison L1 | 0.889 |
| lighting comparison L2 | 1.000 |
| lighting diagnosis L1 | 1.000 |
| lighting diagnosis L2 | 0.889 |
| lighting status L1 | 1.000 |
| lighting status L2 | 1.000 |
| lighting summary L1 | 1.000 |
| lighting summary L2 | 1.000 |
| occupancy comparison L1 | 1.000 |
| occupancy comparison L2 | 0.889 |
| occupancy diagnosis L1 | 1.000 |
| occupancy diagnosis L2 | 1.000 |
| occupancy status L1 | 1.000 |
| occupancy status L2 | 0.889 |
| occupancy summary L1 | 1.000 |
| occupancy summary L2 | 1.000 |
| thermal comparison L1 | 1.000 |
| thermal comparison L2 | 0.944 |
| thermal diagnosis L1 | 1.000 |
| thermal diagnosis L2 | 0.833 |
| thermal explanation L1 | 1.000 |
| thermal explanation L2 | 1.000 |
| thermal status L1 | 1.000 |
| thermal status L2 | 1.000 |
| thermal summary L1 | 1.000 |
| thermal summary L2 | 1.000 |
| thermal verification L1 | 0.778 |
| thermal verification L2 | 1.000 |

### rich: per-class spread over 3 repeats (mean, min, max)

| class | mean | min | max |
|---|---:|---:|---:|
| e_comparison_1 | 1.00 | 1.00 | 1.00 |
| e_comparison_2 | 1.00 | 1.00 | 1.00 |
| e_diagnosis_1 | 1.00 | 1.00 | 1.00 |
| e_diagnosis_2 | 1.00 | 1.00 | 1.00 |
| e_explanation_1 | 1.00 | 1.00 | 1.00 |
| e_explanation_2 | 0.67 | 0.67 | 0.67 |
| e_status_1 | 1.00 | 1.00 | 1.00 |
| e_summary_1 | 1.00 | 1.00 | 1.00 |
| e_summary_1_weekday | 1.00 | 1.00 | 1.00 |
| e_summary_2 | 1.00 | 1.00 | 1.00 |
| l_comparison_1 | 0.89 | 0.67 | 1.00 |
| l_comparison_2 | 1.00 | 1.00 | 1.00 |
| l_diagnosis_1 | 1.00 | 1.00 | 1.00 |
| l_diagnosis_2 | 0.89 | 0.67 | 1.00 |
| l_status_1 | 1.00 | 1.00 | 1.00 |
| l_status_2 | 1.00 | 1.00 | 1.00 |
| l_summary_1 | 1.00 | 1.00 | 1.00 |
| l_summary_2 | 1.00 | 1.00 | 1.00 |
| o_comparison_1 | 1.00 | 1.00 | 1.00 |
| o_comparison_2 | 0.89 | 0.67 | 1.00 |
| o_diagnosis_1 | 1.00 | 1.00 | 1.00 |
| o_diagnosis_2 | 1.00 | 1.00 | 1.00 |
| o_status_1 | 1.00 | 1.00 | 1.00 |
| o_status_2 | 0.89 | 0.67 | 1.00 |
| o_summary_1 | 1.00 | 1.00 | 1.00 |
| o_summary_2 | 1.00 | 1.00 | 1.00 |
| q_comparison_1 | 0.89 | 0.67 | 1.00 |
| q_comparison_2 | 1.00 | 1.00 | 1.00 |
| q_diagnosis_1 | 1.00 | 1.00 | 1.00 |
| q_diagnosis_2 | 1.00 | 1.00 | 1.00 |
| q_explanation_1 | 1.00 | 1.00 | 1.00 |
| q_explanation_2 | 0.67 | 0.33 | 1.00 |
| q_status_1 | 1.00 | 1.00 | 1.00 |
| q_status_2 | 1.00 | 1.00 | 1.00 |
| q_summary_1 | 1.00 | 1.00 | 1.00 |
| q_summary_2 | 1.00 | 1.00 | 1.00 |
| q_verification_1 | 1.00 | 1.00 | 1.00 |
| q_verification_2 | 0.89 | 0.67 | 1.00 |
| t_comparison_1 | 1.00 | 1.00 | 1.00 |
| t_comparison_2 | 0.89 | 0.67 | 1.00 |
| t_comparison_2hop | 1.00 | 1.00 | 1.00 |
| t_diagnosis_1 | 1.00 | 1.00 | 1.00 |
| t_diagnosis_2 | 0.83 | 0.50 | 1.00 |
| t_explanation_1 | 1.00 | 1.00 | 1.00 |
| t_explanation_2 | 1.00 | 1.00 | 1.00 |
| t_status_1 | 1.00 | 1.00 | 1.00 |
| t_status_2 | 1.00 | 1.00 | 1.00 |
| t_summary_1 | 1.00 | 1.00 | 1.00 |
| t_summary_2 | 1.00 | 1.00 | 1.00 |
| t_verification_1 | 0.78 | 0.67 | 1.00 |
| t_verification_2 | 1.00 | 1.00 | 1.00 |

Added classes with no instance at rich: none
