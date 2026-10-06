# A constant guesser at the metered profile of the sweep

Versions as in scripts/constant_baseline.py. Instances passed out of 152 (456 questions with the 3 repeats); the reference agent's accuracy at this profile is in run8.md.

| version | instances passed | share |
|---|---:|---:|
| best in hindsight | 98 | 0.645 |
| a priori (0 / false / most common name) | 50 | 0.329 |
| leave-one-out | 54 | 0.355 |

## Per class

| class | answer | instances | hindsight | a priori | leave-one-out | agent (mean over repeats) | truths |
|---|---|---:|---:|---:|---:|---:|---|
| e_comparison_1 | boolean | 3 | 2 | 1 | 0 | 1.00 | True, True, False |
| e_comparison_2 | number | 3 | 1 | 0 | 0 | 1.00 | -32276795965.422997, 385870507.972992, -49760669733.04101 |
| e_diagnosis_1 | entity | 3 | 1 | 1 | 0 | 1.00 | 2018-01-19, 2018-04-28, 2018-10-06 |
| e_diagnosis_2 | number | 3 | 2 | 0 | 2 | 1.00 | 14, 7, 7 |
| e_explanation_1 | number | 3 | 1 | 0 | 0 | 1.00 | 0.183923, 0.450639, 1.546197 |
| e_explanation_2 | entity | 3 | 2 | 2 | 2 | 0.67 | occupied, unoccupied, occupied |
| e_status_1 | number | 3 | 1 | 0 | 0 | 1.00 | 86683293069.698, 102906277531.81, 107686340076.115 |
| e_summary_1 | number | 3 | 1 | 0 | 0 | 1.00 | 5218343476.758, 5816014956.186, 4292294728.16 |
| e_summary_1_weekday | number | 3 | 2 | 0 | 0 | 1.00 | 51899382794.66714, 93268641614.19687, 96344440176.63391 |
| e_summary_2 | number | 3 | 3 | 0 | 2 | 1.00 | 0.055149, 0.027624, 0.029497 |
| l_comparison_1 | boolean | 3 | 2 | 1 | 0 | 0.89 | False, True, True |
| l_comparison_2 | entity | 3 | 2 | 2 | 2 | 1.00 | Core_bottom, Core_bottom, Core_mid |
| l_diagnosis_1 | entity | 3 | 3 | 3 | 3 | 1.00 | Basement, Basement, Basement |
| l_diagnosis_2 | number | 3 | 2 | 0 | 1 | 0.89 | 6, 12, 7 |
| l_status_1 | number | 3 | 1 | 0 | 0 | 1.00 | 17.592, 791.047, 316.631 |
| l_status_2 | boolean | 3 | 3 | 0 | 3 | 1.00 | True, True, True |
| l_summary_1 | number | 3 | 1 | 0 | 0 | 1.00 | 36.481458, 153.917833, 477.10775 |
| l_summary_2 | number | 3 | 2 | 0 | 1 | 1.00 | 548757007.2, 3122100.0, 3245868.0 |
| o_comparison_1 | boolean | 3 | 2 | 1 | 0 | 1.00 | True, False, True |
| o_comparison_2 | number | 3 | 1 | 0 | 0 | 0.89 | 11.678182, -4.749091, 7.064727 |
| o_diagnosis_1 | number | 3 | 2 | 0 | 0 | 1.00 | 10, 10, 6 |
| o_diagnosis_2 | number | 3 | 3 | 0 | 3 | 1.00 | 7, 7, 7 |
| o_status_1 | number | 3 | 1 | 0 | 0 | 1.00 | 10.328, 1.851, 142.122 |
| o_status_2 | boolean | 3 | 2 | 1 | 0 | 0.89 | True, False, True |
| o_summary_1 | number | 3 | 2 | 0 | 0 | 1.00 | 16.757, 16.757, 10.799 |
| o_summary_2 | number | 3 | 3 | 0 | 2 | 1.00 | 8.508818, 8.607636, 8.508818 |
| q_comparison_1 | boolean | 3 | 2 | 2 | 2 | 0.89 | False, False, True |
| q_comparison_2 | entity | 3 | 1 | 1 | 0 | 1.00 | CondPump01, SupplyFan_AHU03, Chiller02 |
| q_diagnosis_1 | entity | 3 | 3 | 3 | 3 | 1.00 | Chiller01, Chiller01, Chiller01 |
| q_diagnosis_2 | entity | 3 | 1 | 1 | 0 | 1.00 | HWPump01, Chiller01, CHWPump01 |
| q_explanation_1 | number | 3 | 1 | 0 | 0 | 1.00 | -42643220.4, 34059042.0, -46143946.8 |
| q_explanation_2 | entity | 3 | 2 | 2 | 2 | 0.67 | occupied, unoccupied, occupied |
| q_status_1 | number | 3 | 1 | 1 | 0 | 1.00 | 0.0, 154568.496, 45181.763 |
| q_status_2 | number | 3 | 1 | 0 | 0 | 1.00 | 1.0, 0.141024, 0.249156 |
| q_summary_1 | number | 3 | 1 | 0 | 0 | 1.00 | 85848.641333, 3357.878, 7135.251417 |
| q_summary_2 | number | 3 | 2 | 2 | 2 | 1.00 | 0, 5, 0 |
| q_verification_1 | boolean | 3 | 2 | 2 | 2 | 1.00 | False, False, True |
| q_verification_2 | boolean | 3 | 2 | 2 | 2 | 0.89 | False, True, False |
| t_comparison_1 | boolean | 3 | 2 | 1 | 0 | 1.00 | True, True, False |
| t_comparison_2 | number | 3 | 2 | 0 | 1 | 0.89 | -0.899, -3.0, -3.001 |
| t_comparison_2hop | entity | 3 | 2 | 2 | 2 | 1.00 | Perimeter_mid_ZN_2, Perimeter_top_ZN_1, Perimeter_mid_ZN_2 |
| t_diagnosis_1 | entity | 3 | 3 | 3 | 3 | 1.00 | DataCenter_basement_ZN_6, DataCenter_basement_ZN_6, DataCenter_basement_ZN_6 |
| t_diagnosis_2 | entity | 2 | 2 | 2 | 2 | 0.83 | Perimeter_bot_ZN_4, Perimeter_bot_ZN_4 |
| t_explanation_1 | number | 3 | 2 | 2 | 1 | 1.00 | 1.510292, -0.35725, -0.001208 |
| t_explanation_2 | entity | 3 | 3 | 3 | 3 | 1.00 | increase, increase, increase |
| t_status_1 | number | 3 | 2 | 0 | 0 | 1.00 | 27.0, 27.001, 24.0 |
| t_status_2 | number | 3 | 3 | 3 | 2 | 1.00 | -0.001, 0.002, -0.001 |
| t_summary_1 | number | 3 | 3 | 0 | 2 | 1.00 | 24.231333, 24.075167, 24.32575 |
| t_summary_2 | number | 3 | 3 | 3 | 2 | 1.00 | 0, 1, 0 |
| t_verification_1 | boolean | 3 | 2 | 2 | 2 | 0.78 | False, False, True |
| t_verification_2 | boolean | 3 | 2 | 1 | 0 | 1.00 | False, True, True |
