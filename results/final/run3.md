# Comparison models (Figure 8)

AI failure by model. `large_office__2a_tampa`, full store, linked graph, the bank's first 35 classes (seed 0, 3 instances), 1 repeat.
Three classes (q_status_1, q_status_2, q_comparison_2) were re-run for every model after a correction to
how their questions name locations. The reference row is `qwen3.8-27b-128k` from the sweep at the rich
profile, first repeat only.

| model | episodes | accuracy | answered | abstained | no_answer | error | mean s |
|---|---:|---:|---:|---:|---:|---:|---:|
| qwen3.8-27b-128k (reference) | 66 | 0.985 | 66 | 0 | 0 | 0 | 70 |
| gemma4-31b-128k | 66 | 0.879 | 59 | 1 | 6 | 0 | 242 |
| qwen2.5-32b-32k | 66 | 0.061 | 51 | 13 | 2 | 0 | 30 |
| gemma2:9b | 66 | 0.000 | 0 | 0 | 0 | 66 | 2 |
| llama3.1-8b-128k | 66 | 0.000 | 2 | 5 | 59 | 0 | 12 |
| mistral-nemo-12b-128k | 66 | 0.000 | 0 | 0 | 66 | 0 | 10 |

Harness errors, first per model:

- `gemma2:9b`: HTTPError: HTTP Error 400: Bad Request
