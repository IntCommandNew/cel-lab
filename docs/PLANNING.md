# CelLab - Sprint Planning

Each laboratory deliverable is treated as the end of a sprint. Laboratories are held on **Fridays**
(L6 = Friday 6 November 2026, earlier/later labs one week apart).

## Calendar

| Lab | Date | Event |
| --- | --- | --- |
| L1 | Fri 2 Oct 2026 | Introduction |
| L2 | Fri 9 Oct 2026 | Project presentation |
| L3 | Fri 16 Oct 2026 | **Deliverable 1** - team & technical solutions (done) |
| L4 | Fri 23 Oct 2026 | Written test 1 |
| L5 | Fri 30 Oct 2026 | Discussion of Deliverable 2 |
| L6 | Fri 6 Nov 2026 | **Deliverable 2** - automaton model, storage & recovery |
| L7 | Fri 13 Nov 2026 | Written test 2 |
| L8 | Fri 20 Nov 2026 | Project progress check |
| L9 | Fri 27 Nov 2026 | Discussion of Deliverable 3 |
| L10 | Fri 4 Dec 2026 | Written test 3 |
| L11 | Fri 11 Dec 2026 | **Deliverable 3** - dataset + NN/RL experiment |
| L12 | Fri 18 Dec 2026 | Discussion of Deliverable 4 |
| - | 21 Dec - 3 Jan | Winter break |
| L13 | Fri 8 Jan 2027 | **Deliverable 4** - natural-language parsing |
| L14 | Fri 15 Jan 2027 | **Final presentation & evaluation** |

## Sprints at a glance

| Sprint | Dates | Length | Goal / deliverable |
| --- | --- | --- | --- |
| 1 | -> 16 Oct 2026 | - | D1: team & technical solutions - **done** (presented separately) |
| 2 | 17 Oct -> **6 Nov 2026** | 3 weeks | D2: automaton model, engine, storage & recovery, tested on 2-3 automata |
| 3 | 7 Nov -> **11 Dec 2026** | 5 weeks | D3: dataset + NN experiment; also all 5 analysis questions and GUI v1 (shown at L8) |
| 4 | 12 Dec 2026 -> **8 Jan 2027** | 4 weeks (incl. break) | D4: deterministic NL parser integrated in the GUI |
| Release | 9 Jan -> **15 Jan 2027** | 1 week | Hardening, documentation, presentation |

The GUI and the analysis questions are not separate deliverables but are needed for the final grade,
so they are scheduled in Sprint 3 where there is the most time.

---

## Sprint 2 - Automaton model & simulation core (due L6, 6 Nov 2026)

**Deliverable:** world state and rules, experiment parameters, state storage and recovery; tested on
2-3 automata (read the current generation, apply the rules, produce the new state).

- [x] Repository setup: structure, `pyproject.toml`, VS Code + Claude Code config, README, prompt
      log
- [ ] Formal definition dataclasses + JSON load/save (`cellab.model`)
- [ ] Validator: structural + reference checks, impossible counts (`cellab.model`)
- [ ] Simulation engine: Moore / von Neumann, wrap & fixed boundaries, ordered rules
      (`cellab.engine`)
- [ ] Elementary (1D) lookup rules - Rule 30 (`cellab.engine`)
- [ ] Initial world: manual text grid, random with seed, centre cell (`cellab.engine`)
- [ ] Experiment parameters + history modes (all / every k / final) + hashes
- [ ] Storage & recovery: save run folder, reload, resume (`cellab.storage`)
- [ ] Example definitions in `examples/automata/`: Game of Life, Brian's Brain, Rule 30 (+ Forest
      Fire)
- [ ] Tests: blinker/glider (Life), Brian's Brain known step, Rule 30 first rows, save -> load ->
      resume
- [ ] Small CLI or notebook demo for the presentation (load definition -> step -> print grid)

## Sprint 3 - Analysis, GUI v1, dataset & NN (due L11, 11 Dec 2026)

**Deliverable:** a dataset of generations and a NN (or RL) experiment run on it.

*By L8 (20 Nov) - progress check:*

- [ ] Analysis engine: state after N (with cycle jump-ahead), stability, pattern occurrence,
      cell count, cycle detection - with confirmed / not-found / not-applicable statuses
- [ ] Streamlit GUI v1: load/edit definition (JSON/table), initial world, parameters, run,
      generation slider + playback, population chart, analysis form, saved runs browser
- [ ] More automata: Cyclic CA, Forest Fire, Voter, Crystal growth, SIR (deterministic)

*By L11 (11 Dec):*

- [ ] Probabilistic rules with seeded RNG (stochastic Forest Fire / SIR)
- [ ] Dataset generator script (`experiments/`), seeded and documented; sample committed
- [ ] NN experiment: CNN learns transition rule; baselines; per-cell / per-grid / rollout metrics
- [ ] Optional Q/A dataset from the analysis engine (stabilises? period?) + classifier
- [ ] Experiment report `docs/EXPERIMENTS.md` (setup, results, conclusions)

## Sprint 4 - Natural-language parsing (due L13, 8 Jan 2027)

**Deliverable:** parsing the natural-language description of an automaton.

- [ ] Normaliser: case, punctuation, number words, spelling variants, verb & state synonyms
- [ ] Templates: world size, boundary, states, neighbourhood, transition rules, conditions, presets
- [ ] Initial-world sentences (random density, centre cell, named patterns)
- [ ] Error reporting with "did you mean" suggestions; reported defaults; no invented rules
- [ ] Canonical English generator (definition -> text) for confirmation & round-trip tests
- [ ] Test corpus: >= 3 phrasings for each supported automaton + ambiguous/unsupported cases
- [ ] GUI: "Describe" tab - text -> interpretation -> errors/warnings -> confirm/edit -> simulate
- [ ] Supported-language guide `docs/LANGUAGE.md` for users
- [ ] *Stretch:* analysis questions asked in natural language ("how many alive cells after 50
      steps?")

## Release - Final presentation (L14, 15 Jan 2027)

- [ ] End-to-end check of every example automaton through the GUI
- [ ] Performance limits (max grid size / generations) and clear messages when hit
- [ ] *Stretch:* Langton's Ant or Sandpile
- [ ] README: complete installation, configuration and usage; screenshots
- [ ] PROMPTS.md complete for every member; AI usage section final
- [ ] Presentation slides + live demo script
