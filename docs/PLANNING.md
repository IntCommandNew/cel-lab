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

## Sprint 2 - Automaton model, simulation core & GUI preview (due L6, 6 Nov 2026)

**Deliverable:** world state and rules, experiment parameters, state storage and recovery; tested on
2-3 automata (read the current generation, apply the rules, produce the new state).

**Also in this sprint:** a first GUI that already has the main ideas and components of the final
one, so we can see how it looks, feels and works. Three ways to get an automaton definition (the
JSON that the natural-language parser will produce in Sprint 4): pick a preset, build it with a
form, or paste/upload a JSON. Every definition is validated, then it can be run.

Built in chunks; each chunk ends with passing tests and is checked before the next one starts.

- [x] Repository setup: structure, `pyproject.toml`, VS Code + Claude Code config, README, prompt
      log
- [x] **Chunk 1 - Model:** definition dataclasses + JSON load/save, validator (structural,
      reference, semantic checks with field paths), plain-English summary, presets (Game of Life,
      Brian's Brain, Rule 30, Forest Fire); unit tests
- [ ] **Chunk 2 - Engine:** neighbour counting (Moore / von Neumann, wrap / fixed boundary),
      ordered rules, elementary (1D) rules, initial worlds (text grid, random with seed, centre
      cell); unit tests with known patterns (blinker, glider, Brian's Brain step, Rule 30 rows)
- [ ] **Chunk 3 - Simulation & storage:** experiment parameters, history modes (all / every k /
      final), generation hashes, save run folder, reload, resume; integration tests (save -> load
      -> resume equals an uninterrupted run)
- [ ] **Chunk 4 - GUI shell & definitions:** theme, layout, preset picker, JSON paste/upload with
      validation messages, readable summary of the definition; Streamlit `AppTest` tests
- [ ] **Chunk 5 - GUI definition builder:** form for grid, states, neighbourhood and rules that
      produces the JSON (preview + download); `AppTest` tests
- [ ] **Chunk 6 - GUI run & inspect:** initial world, run parameters, run, grid viewer with
      generation slider, population chart, save / load runs; `AppTest` tests + manual check

## Sprint 3 - Analysis, GUI v1, dataset & NN (due L11, 11 Dec 2026)

**Deliverable:** a dataset of generations and a NN (or RL) experiment run on it.

*By L8 (20 Nov) - progress check:*

- [ ] Analysis engine: state after N (with cycle jump-ahead), stability, pattern occurrence,
      cell count, cycle detection - with confirmed / not-found / not-applicable statuses
- [ ] Streamlit GUI v1: refine the Sprint 2 preview (playback, analysis form, saved runs
      browser, design polish)
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
