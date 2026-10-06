# Original and linked graph (Section 5.1)

Graph heterogeneity: the published kg.ttl against kg_linked.ttl (bara.graphfix). `large_office__2a_tampa`, equipment and energy-comparison classes, bank seed 0 (built on the linked graph,
so both runs get the same questions), 3 instances, 3 repeats each, qwen3.8-27b-128k.

| graph | episodes | accuracy | per-repeat accuracy |
|---|---:|---:|---|
| published | 36 | 1.000 | 1.000, 1.000, 1.000 |
| linked | 36 | 1.000 | 1.000, 1.000, 1.000 |

Linked minus published, per repeat: +0.000, +0.000, +0.000; mean +0.000, range +0.000 to +0.000.
