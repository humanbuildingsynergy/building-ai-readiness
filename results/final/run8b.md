# Other eight buildings of the corpus (Table 10)

All 64 classes of the bank, full store, linked graph, bank seed 0, 3 instances per class, 1 repeat, qwen3.8-27b-128k.
Cells: accuracy (episodes). Three classes (q_status_1, q_status_2, q_comparison_2) carry their rows from a re-run after a correction to how their questions name locations.

| building | ceiling | episodes | accuracy (episodes) | A (mean rung) | thermal | energy | equipment | occupancy | lighting |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| large_office__4a_newyork | 49/76 | 149 | 0.953 | 0.952 | 0.95 (37) | 0.93 (28) | 0.97 (36) | 0.96 (24) | 0.96 (24) |
| large_office__5a_buffalo | 49/76 | 153 | 0.935 | 0.932 | 0.95 (39) | 0.93 (30) | 0.89 (36) | 0.96 (24) | 0.96 (24) |
| medium_office__2a_tampa | 49/76 | 147 | 0.939 | 0.940 | 0.95 (39) | 0.93 (30) | 0.88 (33) | 0.96 (24) | 1.00 (21) |
| medium_office__4a_newyork | 49/76 | 147 | 0.959 | 0.957 | 0.92 (39) | 1.00 (30) | 0.97 (33) | 0.92 (24) | 1.00 (21) |
| medium_office__5a_buffalo | 49/76 | 149 | 0.933 | 0.924 | 0.95 (39) | 1.00 (30) | 0.89 (35) | 0.83 (24) | 1.00 (21) |
| small_office__2a_tampa | 37/76 | 113 | 0.956 | 0.959 | 0.94 (36) | 0.93 (29) | — | 0.96 (24) | 1.00 (24) |
| small_office__4a_newyork | 37/76 | 114 | 0.912 | 0.910 | 0.94 (36) | 0.93 (30) | — | 0.75 (24) | 1.00 (24) |
| small_office__5a_buffalo | 37/76 | 114 | 0.956 | 0.955 | 0.97 (36) | 1.00 (30) | — | 0.92 (24) | 0.92 (24) |

accuracy (episodes) = share of graded episodes answered correctly, pooled; A = mean of the
per-rung accuracies over the probed rungs. A across the eight: 0.910 to 0.959.
