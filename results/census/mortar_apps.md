# Mortar applications on the census graphs

37 graphs with linked series; 10 applications of mortar-analytics (df48efc) that compute something, each by its own qualify queries (vocabulary translated as in scripts/mortar_apps.py), linked points only.

- Spearman correlation of the number of applications that can run with the linked C_ans: **0.62** (37 graphs).
- Graphs that can run each application: zone_comfort_evaluation 23, compare_sensors_against_setpoints 16, rogue_zone_airflow 1, simultaneous_heating_cooling_ahus 0, possibly_inefficient_zones 0, energy_consumption_baseline 0, dr_evaluation 0, weekday_mean_energy 0, meter_data_example 0, occupancy_energy_correlation 0.
- Largest disagreements (rank of C_ans minus rank of the application count, as a share of 37): ceiling ranks higher: bldg28 (+0.58), bldg26 (+0.58), bldg19 (+0.58), bldg36 (+0.36); applications rank higher: bldg30 (-0.45), bldg16 (-0.27), bldg18 (-0.27), bldg20 (-0.27).

| graph | C_ans linked | applications | which |
|---|---:|---:|---|
| bldg15 | 0.500 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg11 | 0.395 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg13 | 0.395 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg34 | 0.395 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg40 | 0.395 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg32 | 0.316 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg36 | 0.250 | 1 | zone_comfort_evaluation |
| bldg19 | 0.211 | 0 | - |
| bldg26 | 0.211 | 0 | - |
| bldg28 | 0.211 | 0 | - |
| bldg1 | 0.184 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg22 | 0.184 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg27 | 0.184 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg4 | 0.184 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg9 | 0.184 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| Site_B | 0.158 | 1 | zone_comfort_evaluation |
| bldg16 | 0.158 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg18 | 0.158 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg2 | 0.158 | 0 | - |
| bldg20 | 0.158 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg5 | 0.158 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg6 | 0.158 | 2 | zone_comfort_evaluation, compare_sensors_against_setpoints |
| bldg10 | 0.092 | 1 | zone_comfort_evaluation |
| bldg21 | 0.092 | 0 | - |
| bldg25 | 0.092 | 1 | zone_comfort_evaluation |
| bldg29 | 0.092 | 1 | zone_comfort_evaluation |
| bldg30 | 0.092 | 2 | zone_comfort_evaluation, rogue_zone_airflow |
| bldg8 | 0.092 | 1 | zone_comfort_evaluation |
| bldg14 | 0.000 | 0 | - |
| bldg17 | 0.000 | 0 | - |
| bldg23 | 0.000 | 0 | - |
| bldg24 | 0.000 | 0 | - |
| bldg3 | 0.000 | 0 | - |
| bldg31 | 0.000 | 0 | - |
| bldg33 | 0.000 | 0 | - |
| bldg35 | 0.000 | 0 | - |
| bldg7 | 0.000 | 0 | - |
