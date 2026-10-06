# Worked examples of the question bank

`large_office__2a_tampa`, rich profile (the sweep's bank, seed 0), qwen3.8-27b-128k, 3 repeats each. The instance of each
class is the first one the agent answered correctly in every repeat; the last is a typical miss.

## an L1 number: `t_status_1` (thermal / status, L1)

> What was the air temperature in zone DataCenter_basement_ZN_6 at 2018-01-02 08:00, in °C?
>
> Answer shape: `{"value": <number>}`

- Requires: T. Ground truth: `27.0`. Grader: number within ±0.5.
- Truths of the class's three instances: `27.0`, `27.001`, `24.0`.
- Repeat 0: answered, answer {"value": 27}, grade 1.
- Repeat 1: answered, answer {"value": 27}, grade 1.
- Repeat 2: answered, answer {"value": 27}, grade 1.

## an L2 difference: `t_comparison_2` (thermal / comparison, L2)

> At 2018-01-14 16:00, what was the air temperature of zone Basement minus that of zone DataCenter_top_ZN_6 (the HVAC zone with this label, not the room that shares it), in °C? A positive value means Basement was warmer.
>
> Answer shape: `{"value": <number>}`

- Requires: T. Ground truth: `-3.0`. Grader: number within ±0.5.
- Truths of the class's three instances: `-0.899`, `-3.0`, `-3.001`.
- Repeat 0: answered, answer {"value": -3}, grade 1.
- Repeat 1: answered, answer {"value": -3}, grade 1.
- Repeat 2: answered, answer {"value": -3}, grade 1.

## a yes/no verification: `t_verification_2` (thermal / verification, L2)

> Did zone Perimeter_mid_ZN_4 stay within its own heating and cooling setpoints at every hourly value on 2018-07-04?
>
> Answer shape: `{"value": <true|false>}`

- Requires: T, Sp. Ground truth: `False`. Grader: yes/no: exact.
- Truths of the class's three instances: `False`, `True`, `True`.
- Repeat 0: answered, answer {"value": false}, grade 1.
- Repeat 1: answered, answer {"value": false}, grade 1.
- Repeat 2: answered, answer {"value": false}, grade 1.

## an entity answer (lighting): `l_comparison_2` (lighting / comparison, L2, two hops)

> In this building the electric power sensor attached to a zone meters that zone's lighting. Among zones Core_bottom, Perimeter_bot_ZN_4, Perimeter_top_ZN_1, which one used the most lighting energy on 2018-10-12? Answer with the zone's name.
>
> Answer shape: `{"entity": "<name>"}`

- Requires: Lgt. Ground truth: `Core_bottom`. Grader: entity: the name, or any name the graph ties to the entity (case and punctuation ignored).
- Truths of the class's three instances: `Core_bottom`, `Core_bottom`, `Core_mid`.
- Repeat 0: answered, answer {"entity": "Core_bottom"}, grade 1.
- Repeat 1: answered, answer {"entity": "Core_bottom"}, grade 1.
- Repeat 2: answered, answer {"entity": "Core_bottom"}, grade 1.

## a class that spans two KG hops: `t_comparison_2hop` (thermal / comparison, L2, two hops)

> Among the zones served by air handler AHU02, which zone had the highest air temperature at 2018-10-09 11:00?
>
> Answer shape: `{"entity": "<name>"}`

- Requires: T. Ground truth: `Perimeter_mid_ZN_2`. Grader: entity: the name, or any name the graph ties to the entity (case and punctuation ignored).
- Truths of the class's three instances: `Perimeter_mid_ZN_2`, `Perimeter_top_ZN_1`, `Perimeter_mid_ZN_2`.
- Repeat 0: answered, answer {"entity": "Zone_F3_Z03"}, grade 1.
- Repeat 1: answered, answer {"entity": "Zone_F3_Z03"}, grade 1.
- Repeat 2: answered, answer {"entity": "Zone_F3_Z03"}, grade 1.

## an energy number: `e_summary_1` (energy / summary, L1)

> What was the highest hourly whole-building electricity use in 2018-10, in joules per hour?
>
> Answer shape: `{"value": <number>}`

- Requires: Whole. Ground truth: `5218343476.758`. Grader: number within ±2%.
- Truths of the class's three instances: `5218343476.758`, `5816014956.186`, `4292294728.16`.
- Repeat 0: answered, answer {"value": 5218343476.758}, grade 1.
- Repeat 1: answered, answer {"value": 5218343476.758}, grade 1.
- Repeat 2: answered, answer {"value": 5218343476.758}, grade 1.

## an equipment number: `q_summary_1` (equipment / summary, L1)

> What was the mean electrical power of Chiller01 on 2018-10-10 over all 24 hourly values, in watts?
>
> Answer shape: `{"value": <number>}`

- Requires: Pwr. Ground truth: `85848.641333`. Grader: number within ±1 or ±2% (the larger).
- Truths of the class's three instances: `85848.641333`, `3357.878`, `7135.251417`.
- Repeat 0: answered, answer {"value": 85848.64}, grade 1.
- Repeat 1: answered, answer {"value": 85848.64133333333}, grade 1.
- Repeat 2: answered, answer {"value": 85848.64133333333}, grade 1.

## an occupancy number: `o_status_1` (occupancy / status, L1)

> How many people were in zone Perimeter_top_ZN_2 at 2018-10-11 09:00?
>
> Answer shape: `{"value": <number>}`

- Requires: Occ. Ground truth: `10.328`. Grader: number within ±1 or ±5% (the larger).
- Truths of the class's three instances: `10.328`, `1.851`, `142.122`.
- Repeat 0: answered, answer {"value": 10.328}, grade 1.
- Repeat 1: answered, answer {"value": 10.328}, grade 1.
- Repeat 2: answered, answer {"value": 10.328}, grade 1.

## a typical miss: `t_verification_1` (thermal / verification, L1)

> On 2018-10-25, did zone Perimeter_bot_ZN_4 stay at or below 26 °C at every one of its 24 hourly values?
>
> Answer shape: `{"value": <true|false>}`

- Requires: T. Ground truth: `False`. Grader: yes/no: exact.
- Truths of the class's three instances: `False`, `False`, `True`.
- Repeat 0: abstained, answer —, grade 0.
- Repeat 1: answered, answer {"value": false}, grade 1.
- Repeat 2: abstained, answer —, grade 0.

## an L3 class

No L3 class instantiates on the published BATS building (it has no ActC, ActP, SAT, SpC, Run, Load, CO2 or OAF series).

