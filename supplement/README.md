# BATS v1.0 L3 supplement: separating streams and paired fault scenarios

This folder is part of the reproduction repository of the paper *Which Buildings Are Artificial
Intelligence-Ready? A Measurement-Based Assessment Framework for AI Question Answering and
Actuation* and shares its DOI. It is not a separate record. Its data are licensed CC BY-NC 4.0 (`LICENSE` here), not Apache-2.0 like the code.

A small companion to the **Building AI Testbed Suite (BATS) v1.0** (Zenodo, DOI
10.5281/zenodo.20777376). BATS v1.0 publishes no stream that could tell the causes of its fault
scenarios apart. So cause attribution (level 3 of the readiness canon) could only be tested as an
abstention: the right answer was always "the data cannot tell". This supplement adds two separating
streams and two paired scenarios. Cause attribution can then be tested positively: the same
observation, two different true causes, and one stream that tells them apart.

Everything is for one building, the 90.1-2019 large office in Tampa (climate 2A), BATS id
`large_office__2a_tampa`.

## What is added

| folder | what it is | base | new series |
|---|---|---|---|
| `large_office__2a_tampa__faulted` | BATS v1.0 faulted building (thermostat offsets from 2018-06-15) plus its **scheduled cooling setpoint** (SpC) for Core_bottom | the BATS v1.0 store | 1 |
| `large_office__2a_tampa__act` | the clean building plus the **VAV terminal damper position** (ActP, the terminal actuation response) of all 15 terminals | full store (re-simulation) | 108 (93 + 15) |
| `large_office__2a_tampa__s1r` | **schedule change**: Core_bottom's own heating and cooling setpoint schedules lowered by 1 C from 2018-06-15, with SpC | full store (new simulation) | 94 (93 + 1) |
| `large_office__2a_tampa__s4` | **internal-load step**: a 40 kW always-on equipment load added to Core_mid from 2018-07-01, with ActP | full store (new simulation) | 108 (93 + 15) |
| `large_office__2a_tampa__s3m` | **sensor drift**: Core_mid's temperature reading drifting to +1.0 C from 2018-07-01 to year end, added after the simulation, so the control loop never sees it | `__act` | 1 (the drifted reading) |

Each folder has `points.csv` and `timeseries.csv` (stored gzipped as `timeseries.csv.gz`) in the BATS v1.0 format (same columns, hourly, values
rounded to 3 decimals as in the release). Every folder except `__s3m` has an `addendum.ttl` that
adds the new points and their series references to the BATS graph. `__s3m` adds no point: it
replaces one series of `__act` with the drifted reading. s1r, s3m and s4 also have a `faults.csv`
label in the BATS format. The existing BATS series keep their ids. New ids are deterministic (UUID5).

**Types of the new points.**
- The scheduled setpoint is `brick:Occupied_Air_Temperature_Cooling_Setpoint`, on the zone.
- The damper position is `brick:Damper_Position_Setpoint`, on the VAV (the class the BATS graph
  declares). The series is the simulated position, so the diagnosis stores count it as the actuation
  response (ActP), not the command. Where the BATS graph already
  declares that point (with no series behind it in v1.0), the addendum only adds the reference; where
  it does not, the addendum adds the point.

## The two pairs

| pair | scenario | true cause | look-alike (base streams: zone T, setpoint in effect) | separating stream |
|---|---|---|---|---|
| A | s1 (BATS v1.0) | local override or controller offset | Core_bottom T −0.87 C, setpoint in effect −1.00 C, peer +0.01 C | SpC **+0.00 C** (the schedule did not change) |
| A | s1r | schedule change | Core_bottom T −0.91 C, setpoint in effect −1.00 C, peer +0.01 C | SpC **−1.00 C** (the schedule moved) |
| B | s3m | zone sensor fault | Core_mid reported T +0.75 C, setpoint +0.00 C, peer +0.00 C | damper **+0.000** (the loop saw nothing) |
| B | s4 | local load change | Core_mid reported T +0.67 C, setpoint +0.00 C, peer +0.00 C | damper **+0.180** (opens to meet the load) |

The changes are against the clean building, as means over occupied weekday hours (09:00–17:00):
2018-06-16 to 06-29 for pair A, and 2018-10-01 to 12-31 for pair B.

## How it was made

All simulations are EnergyPlus 22.1, run on the model file that BuildStream, the simulation software
that generated BATS, wrote for BATS v1.0 with the
release's command line (`-w <epw> -d <dir> -r`) and weather file
(USA_FL_Tampa-MacDill.AFB.747880_TMY3). There is one change per run:

- **`__act`:** one output variable added, `Zone Air Terminal VAV Damper Position`. Every other output
  column is identical to a run of the same model without the added variable (213 of 213 columns,
  8,760 hours).
- **`__s1r`:** as `__act`, plus zone-specific copies of the heating and cooling setpoint schedules
  (`SUPP_S1R_HTG`, `SUPP_S1R_CLG`), 1 C lower from 06/15.
- **`__s4`:** as `__act`, plus one `ElectricEquipment` object in Core_mid (40 kW, always on from
  07/01). At that load EnergyPlus reports the building's transformer as overloaded. This is an
  electrical-model check, not a thermal error: the zone and HVAC results are unaffected.
- **SpC for s1** is BuildStream's own simulation output (`CLGSETP_SCH_YES_OPTIMUM` schedule value),
  omitted from the v1.0 release. The supplement's series equals it to the release's rounding.
- **The s3m drift** was written by BuildStream v1.0's labelled telemetry injector (linear drift,
  medium severity, +1.0 C by 2019-01-01).

**Agreement with BATS v1.0.**
- **Faulted building:** the re-simulation reproduces all 93 published series to the release's
  rounding, so the SpC series sits exactly beside them.
- **Clean building:** the published v1.0 store cannot be reproduced exactly from the model files. The
  model files as released, the faulted model with its faults removed, and the same model with its
  faults switched off all give the same output. That output agrees with the published clean building on 65
  of 93 series. The other 28 are HVAC and plant series: zone temperatures by at most 0.063 C, the
  building meter by −0.004% over the year, plant equipment by a mean absolute 0.001–0.9%. The
  supplement's clean-based stores (`__act`, `__s1r`, `__s4`, `__s3m`) are therefore full stores from
  one consistent simulation, and they are not merged with the published clean building.

## Using it

```
python supplement/merge_supplement.py --bats <path to BATS v1.0> --out <folder>
```

This writes the five complete buildings (standard library only; the graph is the BATS graph followed
by the addendum). Inside the repository, `python -m bara.scenarios` runs it for you, and
`bara/supplement.py` is the code that made this supplement. The diagnosis experiment of the paper
also added the inverse of every `brick:hasPoint` and `brick:isPointOf` triple, a standard inference
step.

## License and citation

CC BY-NC 4.0, the same as BATS v1.0 (see `LICENSE`). Please cite BATS v1.0 and this repository
(`CITATION.cff` at the top level). `SHA256SUMS` lists the digest of every file in this folder
(`sha256sum -c SHA256SUMS` from inside it; on macOS, `shasum -a 256 -c SHA256SUMS`).
The simulation inputs are the DOE Commercial Prototype Building Models (energycodes.gov), which are
not redistributed here.
