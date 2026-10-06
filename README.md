# building-ai-readiness

Code, results and data supplement for the paper *Which Buildings Are Artificial Intelligence-Ready?
A Measurement-Based Assessment Framework for AI Question Answering and Actuation* (W. Jung,
University of Arizona; under review).

`bara` stands for Building AI Readiness Assessment. It needs Python 3.11 or later and was tested
on Python 3.14.4.

## Licenses by folder

| folder | what it holds | license |
|---|---|---|
| `bara/`, `scripts/`, `tests/`, top-level files | the code | Apache-2.0 (`LICENSE`) |
| `results/` | deposited run summaries, episode transcripts, tables, census, ceilings | CC BY-NC 4.0 (`results/LICENSE`) |
| `supplement/` | BATS v1.0 L3 supplement: five building folders, `merge_supplement.py`, README, `SHA256SUMS` | CC BY-NC 4.0 (`supplement/LICENSE`) |
| `bara/brick/Brick.ttl` | the Brick ontology 1.4.4, unmodified | BSD-3-Clause (`bara/brick/LICENSE`) |

The whole repository is one Zenodo record with one DOI. It supplements BATS v1.0
(DOI [10.5281/zenodo.20777376](https://doi.org/10.5281/zenodo.20777376)). BATS itself is not
redistributed here: `scripts/fetch_data.py` downloads it.

## What the study measures

A building's instrumentation fixes what an AI agent could possibly answer about it. The paper turns
this into two *readiness ceilings*: answerable readiness (questions over 6 domains × 6 intents, at
three completeness levels, 76 rungs in all) and actuation readiness (what the agent could command).
An agent is then run on question banks built from the building's own graph and data. The ceiling is
split into what the agent realized, AI failure, rungs no question probed, and the data limitation.
The buildings are the nine clean and nine faulted buildings of BATS v1.0 (EnergyPlus prototype
offices with Brick graphs), eight real buildings from Mortar, and a census of 45 real Brick graphs.

Examples for readers are in `examples/`: one full agent episode (`example_episode.md`), worked
examples of each kind of question (`worked_examples.md`), and one BATS instance of every class of the
question bank (`question_bank_examples.csv`, rendered in `question_bank_examples.md`), all written by
`python scripts/examples.py`.

## Three reproduction levels

| level | reproduces | needs | time |
|---|---|---|---|
| 1 tables | the run tables `results/final/run*.md` from the deposited run summaries | CPU, no download | seconds |
| 2 census | the census of 45 real graphs and every ceiling, from fresh public data | CPU, ~45 MB download | ~1–2 min download + ~1 min |
| 3 agent | one agent episode on a BATS building, graded like the study | ~22 GB of GPU memory, Ollama 0.33.3, the reference model | ~1–2 min per episode |

```
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -e ".[test,figures]"
pytest                                            # synthetic and deposit checks, ~1 min
                                                  # (the Mortar-conversion tests need ".[level3]")

python -m bara.reproduce tables                   # level 1

python scripts/fetch_data.py                      # BATS v1.0 (Zenodo), Mortar graphs (Hugging Face), BTS Site B graph (figshare)
python -m bara.reproduce census                   # level 2

ollama create qwen3.8-27b-128k -f scripts/ollama/qwen3.8-27b-128k.Modelfile   # after `ollama pull qwen3.8:27b`
python -m bara.reproduce agent --smoke            # level 3 (fetch_data.py --bats is enough for it)
```

Each level writes into `$BARA_DATA/derived/reproduce/<level>/` (default `./data/derived/reproduce/<level>/`)
and compares its
output with the deposit. Levels 1 and 2 require identical files. Level 3 requires the rebuilt question
to match the deposited episode, and both the deposited answer and the new answer to grade to the
deposited score. The agent samples at temperature 1.0 (below), so a new episode can differ in its
path, and occasionally in its answer. The exit code is 0 only when every check passes.

Data locations can be moved with environment variables: `BARA_DATA` (root), or `BATS_DIR`,
`MORTAR_DIR`, `BTS_DIR`, `DERIVED_DIR` and `MORTAR_GRAPHS_DIR` (the census graphs) one by one.

The generators behind the deposit (`python -m bara.tables`, `python -m bara.census` and the scripts
that write tables or examples) write into `results/` or `examples/` by default, which overwrites the
deposited files. Give them `--out` with a folder under `$DERIVED_DIR` to keep the deposit intact.

## Manuscript item → source

Items are named by their LaTeX label and, in brackets, their number in the submitted manuscript
(the journal may renumber them). "Level 1" means `python -m bara.tables`
(checked by `python -m bara.reproduce tables`); "level 2" means `python -m bara.reproduce census`.
The figures come from `python scripts/figures/make_results_figs.py`. The conceptual figures and
tables (`fig:overview`, `fig:ladder`, `fig:decomp-concept`, `fig:axes`, `fig:design`, `fig:agent`,
`tab:positioning`, `tab:nomenclature`, `tab:outcomes`) are drawn for the paper and have no code
behind them (Figures 1–6; Tables 1, 2 and 5).

| manuscript item | deposited file | how it is produced |
|---|---|---|
| `tab:canon`, `tab:canon-req`, `tab:causes` (Tables 3, 4, B.15) | — | `bara/canon.py` (the canon, its requirement table and cause sets, as data) |
| `tab:actcanon` (Table 6) | — | `bara/census.py` (`ACTUATION`) |
| `tab:profiles` (Table 7) | — | `bara/canon.py` (`PROFILES`) |
| `tab:canon-ex`, `tab:sri` (Tables B.14, A.13) | — | written for the paper; the canon they illustrate is `bara/canon.py` |
| `tab:sweep`, `fig:decomp` (Table 8, Figure 7) | `results/final/run8.md` | level 1; figure `fig_sweep_domains` |
| `tab:cells` (Table B.17) | `results/ceilings.json` (`per_cell` of the sweep building per profile) | level 2 |
| `tab:canon-sens` (Table 9) | — | `python scripts/canon_sensitivity.py` |
| `tab:others` (Table 10) | `results/final/run8b.md` | level 1 |
| `fig:agents` (Figure 8) | `results/final/run3.md` | level 1; figure `fig_agents` |
| `tab:pairs` (Table E.23), the look-alike and separation checks | `supplement/README.md` ("The two pairs") | `python -m bara.supplement checks` re-simulates them (see below) |
| `fig:diag` (Figure 9); pair B re-run with its monitoring-sensor premise stated | `results/final/run4s20.md` (pair A), `results/final/run4s20_premise.md` (pair B), `results/faults/scenarios_supplement_premise.json` | level 1; figure `fig_diagnosis` |
| `tab:scenarios` (Table E.22) | `results/faults/scenarios_supplement.json`, `supplement/README.md` | `python -m bara.scenarios` builds the stores; `python -m bara.supplement checks` re-simulates (see below) |
| `fig:real-plane`, `fig:real-streams`, `tab:census` (Figures 10, 11; Table 11) | `results/census/census_v2.{md,json}` | level 2; figures `fig_real_plane`, `fig_real_streams` |
| `tab:misses` (Table 12) | `results/final/misses_reference.csv` | `python scripts/classify_misses.py` (needs BATS) |
| `tab:brickmap` (Table B.16) | — | `bara/census.py` (`RULES`) |
| `tab:tools` (Table C.18) | — | `bara/agent.py` (`TOOLS`) |
| `lst:prompt` (Listing C.1) | — | `bara/agent.py` (`SYSTEM`) |
| `tab:bank` (Table D.20) | per-class spread in `results/final/run8.md` | `bara/bank.py` (`BANK`); scores level 1 |
| `tab:episode` (Table C.19) | `examples/example_episode.md` | `python scripts/examples.py` |
| `tab:worked` (Table D.21) | `examples/worked_examples.md` | `python scripts/examples.py` |
| real buildings (Mortar), accuracy and usability (Section 5.6) | `results/final/run5.md`, `results/mortar/usability.json` | level 1 |
| graph heterogeneity, published against linked graph (Section 5.1) | `results/final/run6.md` | level 1 |
| unanswerable questions per profile (Section 5.1) | `results/final/run9.md` | level 1 |
| census under alternative mapping rules (Section 5.4, Appendix F) | `results/census/census_sensitivity.md` | `python scripts/census_sensitivity.py` |
| usability-rule sensitivity, Mortar (Section 5.6) | `results/mortar/usability_sensitivity.{md,json}` | `python scripts/usability_sensitivity.py` (needs the Mortar series) |
| the Mortar applications' own queries on the census graphs (Section 5.4, Appendix F) | `results/census/mortar_apps.{md,json}` | `python scripts/mortar_apps.py` |
| the same on the June 2026 revision of the Mortar graphs (`87c3d309`, before the Brick 1.5 update) | `results/census/mortar_apps_june2026.md` | `python scripts/fetch_data.py --mortar-june`; `python -m bara.census --graphs $MORTAR_DIR/graphs_june2026 --out $DERIVED_DIR/census_june2026`; `python scripts/mortar_apps.py --graphs $MORTAR_DIR/graphs_june2026 --census $DERIVED_DIR/census_june2026/census_v2.json --out $DERIVED_DIR/census_june2026/mortar_apps_june2026.md --revision "87c3d309, June 2026"` |
| a constant guesser at the metered profile, no runs (Section 5.1) | `results/final/constant_baseline.md` | `python scripts/constant_baseline.py` |
| largest prompt per run and model against its context window (Appendix C) | `results/final/prompt_sizes.md` | `python scripts/prompt_sizes.py` (the Mortar transcripts are not deposited, so their rows are carried over from the deposited file) |

**Episodes.** The reported tables rest on 3,283 agent episodes. The miss table covers the 2,380 of
them that the reference agent answered on the question bank: the sweep (828), the other eight BATS
buildings (1,086), the eight Mortar buildings (394) and the graph variants (72). It finds 120 wrong
answers. The other 903 are the comparison models (330), the paired diagnosis (240) and the
unanswerable questions (333), which are scored by their own tables. The paired diagnosis is the four
scenarios at 20 repeats (160) and pair B re-run with its monitoring-sensor premise stated (80). The
paper reports pair A from `run4s20.md` and pair B from `run4s20_premise.md`, and keeps the first
pair-B run in `run4s20.md` as a sensitivity result. Every episode except the Mortar ones has its
transcript in `results/agent_runs/` (2,889 transcripts). The Mortar transcripts are not deposited,
because they print values of the Mortar series, which has no stated license.

**Run folders.** Each folder of `results/agent_runs/` holds one block of runs, with a summary per
building and model and one transcript per episode. A transcript's file name ends in the Unix time at
which the episode ran.

| folder | contents | table |
|---|---|---|
| `final1_<profile>` | sweep building, the bank's first 35 classes, 3 repeats | `run8.md` |
| `final8_<profile>` | sweep building, the 29 classes added for the remaining rungs, 3 repeats | `run8.md` |
| `final8c_rich` | sweep building, the three classes re-run after a correction to how their questions name locations (`q_status_1`, `q_status_2`, `q_comparison_2`) | `run8.md` |
| `final2`, `final8b`, `final8c` | the other eight buildings: first 35 classes, added 29 classes, the three re-run classes | `run8b.md` |
| `final3` | comparison models on the sweep building, first 35 classes | `run3.md` |
| `final4s`, `final4s_more` | paired diagnosis, repeats 0–4 and 5–19 | `run4s20.md` |
| `final4s_premise` | pair B with its monitoring-sensor premise, 20 repeats | `run4s20_premise.md` |
| `final5`, `final5sp`, `final5r` | Mortar buildings (summaries only): the bank, its setpoint classes, and two buildings re-run in full at their current data year | `run5.md` |
| `final6_published`, `final6_linked` | original and linked graph | `run6.md` |
| `final9` | unanswerable questions per profile | `run9.md` |

The sweep's profile `rich` is the paper's metered profile: on BATS the two coincide, because the
release has none of the rich profile's added points.

Two kinds of rows stay in the summaries without entering a table. Seventeen Mortar episodes are
excluded: once actuation is split into command (ActC) and response (ActP), their questions no longer
instantiate as posed (on bldg34 two classes are not posed; on bldg15 and bldg11 the class is posed on
other zones). They are listed in `results/mortar/run5_excluded.json`. The summaries of `final5` also
keep 48 rows of two Mortar buildings at their earlier data year, which `final5r` replaces.

**Re-running the agent blocks.** `python -m bara.run <block>` re-runs every episode behind a table
(`sweep`, `others`, `agents`, `mortar`, `graphs`, `pairs`, `premise`, `unanswerable`). It writes summaries in
the deposited format, and `python -m bara.tables --runs data/derived/agent_runs --out data/derived/tables` renders them.
The 3,283 episodes took about 93 GPU-hours on one workstation with two NVIDIA RTX 5000 Ada (32 GB
each). The largest blocks are `others` (~26 h), `sweep` (~19 h), `pairs` (~14 h) and `mortar` (~11 h);
`premise`, the re-run of pair B with its monitoring-sensor premise stated, takes ~8 h. The Mortar
block also needs the Mortar series: `python scripts/fetch_data.py --mortar-series` (3.8 GB, plus
`pip install -e ".[level3]"`).

## Models and sampling

Every episode used a local open model served by Ollama 0.33.3. Each model is an Ollama model with its
context length set by the Modelfile in `scripts/ollama/` (`gemma2:9b` as pulled). `gemma2:9b` has no
tool calling in Ollama, so it could not be run: every one of its episodes ends in a request error.
It is listed in `run3.md` and left out of the agents figure.

| model (Ollama name) | base | digest |
|---|---|---|
| `qwen3.8-27b-128k` (reference) | `qwen3.8:27b` (`22130167c4c20e20c7b71454612966ca8e8171e9b3cc8ab6ce8aa6cbfec79643`), Q4_K_M, num_ctx 131072 | `7a97d65479a18ddf36da0f2156e5009c128213a9a4b17d0fc00b92ac67f87867` |
| `gemma4-31b-128k` | `gemma4:31b`, Q4_K_M, 131072 | `75df2ef1263e2d91e78b029d35c5346f124878e0a55fd444ac784c4920bd0044` |
| `qwen2.5-32b-32k` | `qwen2.5:32b`, Q4_K_M, 32768 | `625077fcab15a3136ab1d963d1dd317e5ce64cd471f520580eaba494deb20579` |
| `llama3.1-8b-128k` | `llama3.1:8b`, Q4_K_M, 131072 | `5b7f19bd7dfc207efb6033e034fed85e2cc2e11fe4c3935f24e4691d274f49e7` |
| `mistral-nemo-12b-128k` | `mistral-nemo:12b`, Q4_0, 131072 | `5681cfa2dbd006d1665a50f576c48cd1a9cea511f2c5851bc35801fa88916616` |
| `gemma2:9b` | as pulled, Q4_0 | `ff02c3702f322b9e075e9568332d96c0a7028002f1a5a056e0a6784320a4db0b` |

Effective sampling settings, through Ollama's chat endpoint (`bara/agent_local.py`):

- temperature 1.0 and top_p 1.0. The endpoint's default top_p overrides the base model's 0.95.
- top_k 20 (the base model's default).
- No seed.
- Thinking on for the reference model. Its reasoning text is not archived; the transcripts hold
  every tool call, tool result and answer.

## Data sources

| source | what is used | where it comes from | license |
|---|---|---|---|
| BATS v1.0 | 9 clean + 9 faulted buildings (graphs and hourly series) | Zenodo 10.5281/zenodo.20777376 | CC BY-NC 4.0 |
| Mortar | 44 Brick graphs; series of 8 buildings (level 3 only) | Hugging Face `gtfierro/mortargraphs`, `gtfierro/mortar` | none stated on the dataset cards; cite the Mortar project (Fierro et al., BuildSys 2018, doi 10.1145/3276774.3276796) |
| BTS | the Site B graph | figshare 10.6084/m9.figshare.28705559 | CC BY 4.0 |

`fetch_data.py` pins every source: the Zenodo and figshare MD5s, and the Hugging Face revisions.
The census and the Mortar agent runs both use the Mortar graphs at the August 2026 revision
(`8844574c`), which migrated them off deprecated Brick classes. Two rules keep that migration from
changing what a graph is credited with:

- A deprecated class counts together with the class Brick names as its replacement
  (`brick:isReplacedBy`, e.g. `Zone_Air_Temperature_Setpoint` and
  `Target_Zone_Air_Temperature_Setpoint`). The census (`census.FOLLOW_REPLACEMENTS`) and the bank's
  roles (`bank.with_replacements`, map in `bara/brick/replacements.json`) both apply it.
- A metered point attached to nothing and feeding nothing counts as no stream class
  (`census.UNATTACHED_METER_IS_SUBMETER = False`).

The deposited Mortar results are per-episode outcomes and scores only; no Mortar series value is
deposited.

## The supplement and its provenance

`supplement/` adds two separating streams (the scheduled cooling setpoint and the VAV damper
position) and two paired fault scenarios for the Tampa large office. With them, cause attribution
(level 3 of the canon) can be tested positively. See `supplement/README.md`.
`python -m bara.scenarios` merges the supplement with BATS v1.0 into the stores of the diagnosis
runs. `bara/supplement.py` is the code that made the supplement. Re-running it needs EnergyPlus 22.1
and the EnergyPlus model files that BuildStream v1.0, the simulation software that generated BATS,
wrote for the release, which are not public. It writes under `$DERIVED_DIR/supplement_build/` and
never into `results/` or `supplement/`. It is
included as provenance and is covered by synthetic tests.

## Layout

```
bara/            canon, census, bank, agent + local client, decompose, graphfix, stores, scenarios,
                 drift, faultbank, mortar, run (agent blocks), tables (level 1), reproduce, supplement
scripts/         fetch_data.py, classify_misses.py, canon_sensitivity.py, census_sensitivity.py,
                 prompt_sizes.py, examples.py, constant_baseline.py, usability_sensitivity.py,
                 mortar_apps.py, figures/, ollama/ (Modelfiles), scrub_paths.py
results/         agent_runs/ (summaries + transcripts), final/ (tables), census/, faults/, mortar/, ceilings.json
supplement/      the BATS v1.0 L3 supplement
examples/        examples for readers (scripts/examples.py)
tests/           synthetic tests and deposit checks
```

`scripts/scrub_paths.py` is how the deposited transcripts were made machine-neutral. Folder paths
became placeholders such as `<BATS_DIR>`. Two tool results in which the agent printed the process
environment were replaced by a note.

## Citation

See `CITATION.cff`. Please cite this repository and BATS v1.0.
