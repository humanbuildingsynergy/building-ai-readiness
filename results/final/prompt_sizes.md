# Largest single-turn prompt per run and per model

Prompt tokens as Ollama reports them for each request, over the episodes the tables use.

| run | model | episodes | covered | largest prompt | window | at or over the window | episode |
|---|---|---:|---:|---:|---:|---:|---|
| final1_minimal | qwen3.8-27b-128k | 36 | 36 | 34100 | 131072 | 0 | large_office__2a_tampa__full__t_comparison_2hop#2__r1 |
| final1_comfort | qwen3.8-27b-128k | 63 | 63 | 23199 | 131072 | 0 | large_office__2a_tampa__full__t_comparison_2hop#2__r0 |
| final1_standard | qwen3.8-27b-128k | 90 | 90 | 22176 | 131072 | 0 | large_office__2a_tampa__full__t_comparison_2hop#1__r2 |
| final1_rich | qwen3.8-27b-128k | 171 | 171 | 32702 | 131072 | 0 | large_office__2a_tampa__full__l_diagnosis_2#1__r0 |
| final8_minimal | qwen3.8-27b-128k | 36 | 36 | 35691 | 131072 | 0 | large_office__2a_tampa__full__t_diagnosis_1#1__r2 |
| final8_comfort | qwen3.8-27b-128k | 51 | 51 | 32422 | 131072 | 0 | large_office__2a_tampa__full__t_diagnosis_1#3__r0 |
| final8_standard | qwen3.8-27b-128k | 96 | 96 | 34506 | 131072 | 0 | large_office__2a_tampa__full__t_diagnosis_2#2__r0 |
| final8_rich | qwen3.8-27b-128k | 258 | 258 | 35199 | 131072 | 0 | large_office__2a_tampa__full__t_diagnosis_1#3__r0 |
| final8c_rich | qwen3.8-27b-128k | 27 | 27 | 25727 | 131072 | 0 | large_office__2a_tampa__full__q_status_1#3__r1 |
| final8c | qwen3.8-27b-128k | 45 | 45 | 22350 | 131072 | 0 | large_office__4a_newyork__full__q_status_1#3__r0 |
| final2 | qwen3.8-27b-128k | 447 | 447 | 35395 | 131072 | 0 | large_office__4a_newyork__full__o_diagnosis_2#1__r0 |
| final8b | qwen3.8-27b-128k | 594 | 594 | 40488 | 131072 | 0 | medium_office__2a_tampa__full__q_summary_2#1__r0 |
| final3 | gemma2_9b | 66 | 66 | 0 | 8192 | 0 | — |
| final3 | gemma4-31b-128k | 66 | 66 | 23369 | 131072 | 0 | large_office__2a_tampa__full__e_summary_1_weekday#3__r0 |
| final3 | llama3.1-8b-128k | 66 | 66 | 2149 | 131072 | 0 | large_office__2a_tampa__full__t_summary_2#2__r0 |
| final3 | mistral-nemo-12b-128k | 66 | 66 | 1991 | 131072 | 0 | large_office__2a_tampa__full__l_summary_2#3__r0 |
| final3 | qwen2.5-32b-32k | 66 | 66 | 2880 | 32768 | 0 | large_office__2a_tampa__full__e_summary_1#1__r0 |
| final6_published | qwen3.8-27b-128k | 36 | 36 | 24201 | 131072 | 0 | large_office__2a_tampa__full__q_comparison_2#3__r1 |
| final6_linked | qwen3.8-27b-128k | 36 | 36 | 21339 | 131072 | 0 | large_office__2a_tampa__full__q_status_1#3__r2 |
| final5 | qwen3.8-27b-128k | 300 | 300 | 34949 | 131072 | 0 | bldg34__full__t_diagnosis_1#1__r0 |
| final5sp | qwen3.8-27b-128k | 87 | 87 | 36546 | 131072 | 0 | bldg40__full__t_diagnosis_2#3__r0 |
| final5r | qwen3.8-27b-128k | 72 | 72 | 23463 | 131072 | 0 | bldg11__full__t_diagnosis_2#1__r0 |
| final4s | qwen3.8-27b-128k | 40 | 40 | 40153 | 131072 | 0 | large_office__2a_tampa__s1r__s1r#rung0__r1 |
| final4s_more | qwen3.8-27b-128k | 120 | 120 | 38112 | 131072 | 0 | large_office__2a_tampa__s4__s4#rung1__r9 |
| final4s_premise | qwen3.8-27b-128k | 80 | 80 | 62031 | 131072 | 0 | large_office__2a_tampa__s3m__s3m#rung0__r9 |
| final9 | qwen3.8-27b-128k | 333 | 333 | 35541 | 131072 | 0 | large_office__2a_tampa__minimal__l_comparison_2#1__r1 |

## Per model

| model | largest prompt | window | episodes at or over the window | episodes | episode |
|---|---:|---:|---:|---:|---|
| qwen3.8-27b-128k | 62031 | 131072 | 0 | 3018 | final4s_premise large_office__2a_tampa__s3m__s3m#rung0__r9 |
| gemma2_9b | 0 | 8192 | 0 | 66 | — |
| gemma4-31b-128k | 23369 | 131072 | 0 | 66 | final3 large_office__2a_tampa__full__e_summary_1_weekday#3__r0 |
| llama3.1-8b-128k | 2149 | 131072 | 0 | 66 | final3 large_office__2a_tampa__full__t_summary_2#2__r0 |
| mistral-nemo-12b-128k | 1991 | 131072 | 0 | 66 | final3 large_office__2a_tampa__full__l_summary_2#3__r0 |
| qwen2.5-32b-32k | 2880 | 32768 | 0 | 66 | final3 large_office__2a_tampa__full__e_summary_1#1__r0 |
