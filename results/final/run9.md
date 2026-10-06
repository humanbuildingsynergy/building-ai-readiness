# Unanswerable questions (Section 5.1)

The data limitation tested on the sweep building. `large_office__2a_tampa`, linked graph, the store restricted to the profile as in the sweep, qwen3.8-27b-128k.
Every class the profile cannot support but the full store can (question and ground truth from the
full store), 1 instance, 3 repeats. The right outcome is an abstention; any answer is an overclaim,
right or wrong. Errors (failed requests to the model) are left out of the rate.

| profile | classes | episodes | abstained | answered (overclaim) | no answer | error | overclaim rate | 95% CI (Wilson) | abstentions naming a lacking stream |
|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| minimal | 43 | 129 | 117 | 8 | 3 | 1 | 0.062 | 0.032–0.118 | 117 / 117 |
| comfort | 38 | 114 | 112 | 0 | 1 | 1 | 0.000 | 0.000–0.033 | 112 / 112 |
| standard | 30 | 90 | 89 | 0 | 1 | 0 | 0.000 | 0.000–0.041 | 89 / 89 |

Classes that drew answers:
- minimal: t_verification_2 3× (right), t_summary_2 2× (wrong), t_status_2 1× (wrong), t_diagnosis_2 1× (wrong), t_explanation_2 1× (right)
