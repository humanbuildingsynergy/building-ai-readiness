# Ceiling census over real Brick graphs

45 graphs, 37 with linked series, 35 of those with at least one canon stream class. Statistics below are over the graphs with linked series. Graph-only and agent-free (`python -m bara.census`). declared = every typed point; linked = points that carry a time-series reference.

- Linked ceiling: min 0.000, median 0.158, max 0.500, 9 distinct values.
- The graph declares more than its linked data supports in 15 of 45 graphs: bldg2, bldg4, bldg5, bldg12, bldg18, bldg21, bldg31, bldg35, bldg37, bldg39, bldg41, bldg42, bldg43, bldg44, Site_B.
- Ranking robustness: 1901 of 2000 random domain weightings reorder at least one pair; 102 of 575 pairs ever flip.

## Numbers used in the paper

- Linked C_ans: median 0.158, max 0.500, 9 distinct values; declared above linked in 15 of 45 graphs.
- Graphs (of the 37 with linked series) linking each class: supply air temperature 32, outside air temperature 31, equipment load 25, run status 23, zone temperature 23, zone setpoint 17, terminal actuation command 16, terminal actuation response 13, end-use submeter 12, equipment power 11, whole-building meter 0, occupancy 1, CO2 1.
- C_act: 0.000 to 0.625, median 0.125; 13 graphs expose no writable setpoint or command.
- Weightings: 1901 of 2000 reorder a pair; 102 of 575 pairs with unequal ceilings ever flip.
- Against the number of linked points: Spearman 0.61, 145 of 573 pairs reversed. Against the number of linked stream classes: 0.83, 64 of 539 reversed.
- C_ans range among graphs linking the same number of stream classes: 0: 0.000-0.000; 2: 0.000-0.000; 3: 0.000-0.158; 4: 0.000-0.092; 5: 0.092-0.250; 6: 0.158-0.211; 7: 0.092-0.184; 8: 0.184-0.316; 10: 0.395-0.395.

## Per graph

| source | building | points | linked | C_ans declared | C_ans linked | C_act | linked stream classes |
|---|---|---:|---:|---:|---:|---:|---|
| mortar | bldg1 | 93 | 82 | 0.184 | 0.184 | 0.375 | ActC ActP OAT Run SAT Sp T |
| mortar | bldg2 | 77 | 76 | 0.211 | 0.158 | 0.000 | ActC Load OAT Pwr SAT Sub |
| mortar | bldg3 | 11 | 10 | 0.000 | 0.000 | 0.000 | OAT SAT |
| mortar | bldg4 | 141 | 138 | 0.395 | 0.184 | 0.625 | ActC ActP Load OAT Run SAT Sp T |
| mortar | bldg5 | 524 | 477 | 0.368 | 0.158 | 0.375 | ActC Load OAT Run SAT Sp T |
| mortar | bldg6 | 635 | 596 | 0.158 | 0.158 | 0.375 | Load OAT Run SAT Sp T |
| mortar | bldg7 | 84 | 73 | 0.000 | 0.000 | 0.000 | Load OAT Run SAT |
| mortar | bldg8 | 165 | 140 | 0.092 | 0.092 | 0.125 | ActC ActP Load OAT Run SAT T |
| mortar | bldg9 | 483 | 474 | 0.184 | 0.184 | 0.375 | ActC ActP Load OAT Run SAT Sp T |
| mortar | bldg10 | 65 | 62 | 0.092 | 0.092 | 0.000 | OAT SAT T |
| mortar | bldg11 | 1269 | 897 | 0.395 | 0.395 | 0.375 | ActC ActP Load OAT Pwr Run SAT Sp Sub T |
| mortar | bldg12 | 588 | 0 | 0.184 | 0.000 | 0.000 | - |
| mortar | bldg13 | 130 | 114 | 0.395 | 0.395 | 0.375 | ActC ActP Load OAT Pwr Run SAT Sp Sub T |
| mortar | bldg14 | 11 | 10 | 0.000 | 0.000 | 0.000 | OAT SAT |
| mortar | bldg15 | 916 | 763 | 0.500 | 0.500 | 0.375 | ActC ActP Load OAT Occ Pwr Run SAT Sp Sub T |
| mortar | bldg16 | 20 | 10 | 0.158 | 0.158 | 0.125 | SAT Sp T |
| mortar | bldg17 | 11 | 9 | 0.000 | 0.000 | 0.000 | Load OAT |
| mortar | bldg18 | 487 | 484 | 0.368 | 0.158 | 0.375 | Load OAT Run SAT Sp T |
| mortar | bldg19 | 59 | 50 | 0.211 | 0.211 | 0.125 | Load OAT Pwr Run SAT Sub |
| mortar | bldg20 | 81 | 70 | 0.158 | 0.158 | 0.375 | Load OAT Run SAT Sp T |
| mortar | bldg21 | 47 | 42 | 0.303 | 0.092 | 0.000 | CO2 Load OAT Run SAT |
| mortar | bldg22 | 53 | 45 | 0.184 | 0.184 | 0.250 | ActC ActP Load OAT SAT Sp T |
| mortar | bldg23 | 32 | 27 | 0.000 | 0.000 | 0.000 | Load OAT SAT |
| mortar | bldg24 | 2 | 2 | 0.000 | 0.000 | 0.000 | - |
| mortar | bldg25 | 19 | 16 | 0.092 | 0.092 | 0.125 | OAT Run SAT T |
| mortar | bldg26 | 42 | 36 | 0.211 | 0.211 | 0.125 | Load OAT Pwr Run SAT Sub |
| mortar | bldg27 | 111 | 75 | 0.184 | 0.184 | 0.250 | ActC ActP OAT SAT Sp T |
| mortar | bldg28 | 84 | 37 | 0.211 | 0.211 | 0.125 | Load OAT Pwr Run SAT Sub |
| mortar | bldg29 | 14 | 12 | 0.092 | 0.092 | 0.000 | OAT SAT T |
| mortar | bldg30 | 505 | 505 | 0.092 | 0.092 | 0.125 | ActC ActP Load OAT Run SAT T |
| mortar | bldg31 | 7 | 3 | 0.158 | 0.000 | 0.000 | - |
| mortar | bldg32 | 712 | 712 | 0.316 | 0.316 | 0.375 | ActC OAT Pwr Run SAT Sp Sub T |
| mortar | bldg33 | 4 | 3 | 0.000 | 0.000 | 0.000 | Load |
| mortar | bldg34 | 262 | 193 | 0.395 | 0.395 | 0.375 | ActC ActP Load OAT Pwr Run SAT Sp Sub T |
| mortar | bldg35 | 78 | 74 | 0.211 | 0.000 | 0.000 | Load SAT |
| mortar | bldg36 | 104 | 104 | 0.250 | 0.250 | 0.125 | ActC Pwr Run Sub T |
| mortar | bldg37 | 2930 | 0 | 0.526 | 0.000 | 0.000 | - |
| mortar | bldg38 | 14 | 0 | 0.000 | 0.000 | 0.000 | - |
| mortar | bldg39 | 92 | 0 | 0.368 | 0.000 | 0.000 | - |
| mortar | bldg40 | 333 | 263 | 0.395 | 0.395 | 0.625 | ActC ActP Load OAT Pwr Run SAT Sp Sub T |
| mortar | bldg41 | 36 | 0 | 0.092 | 0.000 | 0.000 | - |
| mortar | bldg42 | 163 | 0 | 0.184 | 0.000 | 0.000 | - |
| mortar | bldg43 | 266 | 0 | 0.316 | 0.000 | 0.000 | - |
| mortar | bldg44 | 200 | 0 | 0.395 | 0.000 | 0.000 | - |
| bts | Site_B | 852 | 851 | 0.316 | 0.158 | 0.375 | ActP Load OAT Run SAT Sp Sub Sub2 T |
