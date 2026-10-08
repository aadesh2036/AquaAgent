# INSTRUCTIONS.md — Read this before touching ANY module or sub-module

> Audience: every coding agent (and human) working in this repo.
> This file holds **process rules only**. It defines no contracts. Contracts live in [BACKBONE.md](BACKBONE.md) and nowhere else.
> Status of the build lives in [TILL_NOW.md](TILL_NOW.md).

---

## 1. Reading order (mandatory, every session)

| # | File | Why | Required? |
|---|---|---|---|
| 1 | `INSTRUCTIONS.md` (this file) | How to work here | Always |
| 2 | `BACKBONE.md`, read **completely** | The contract: schemas, IDs, units, endpoints, S3 paths, env vars, gates | Always |
| 3 | `docs/modules/NN_<NAME>.md`, your assigned module | What to build, in which order, and how to prove it works | Always |
| 4 | `TILL_NOW.md` | What is already done, what is blocked, which interim decisions apply | Always |
| 5 | `docs/BACKBONE_ISSUES.md` | Why the 1.1.0 decisions were made (all resolved) | When a decision surprises you |
| 6 | `docs/aws/0x_*.md`, `docs/research/WNTR_FEASIBILITY.md` | AWS context (T2) / measured simulation facts | Only when relevant |

Do **not** read other module MDs to "get context". A module MD plus BACKBONE is meant to be self-contained (BACKBONE §0.1). If you need something from another module, it must be in your MD's **§2 Inputs** or **§11 Handoff**. If it isn't there, stop and report it (see §6).

Precedence when documents disagree (BACKBONE §0.5): **BACKBONE.md > module MD > `CONTEXT/AquaAgent_handoff.md` > Simulation Spec v1 > Prototype Guide > README_FOR_SIM.md**. `INSTRUCTIONS.md` and `TILL_NOW.md` never override a contract.

## 2. Vocabulary

- **Module** = one of the ten `docs/modules/NN_*.md` (BACKBONE §4). It owns specific directories (its §4 "Files owned").
- **Sub-module / step** = one numbered step in a module MD's **§6 Implementation plan**. Each step is ≤ 2 h and has a **"done when"** check. You work one step at a time.
- **Gate** = G1–G10 (BACKBONE §12). A module is "done" only when its gate checklist (module MD §9) passes.

## 3. Hard rules (violating any of these is a failed task)

1. **Never change a contract.** Schemas, IDs, units, endpoints, S3 paths, env var names and gates are defined in BACKBONE and coded once in `shared/contracts/` + `shared/units.*`. Import them, never re-declare them. If one is wrong, follow §6.
2. **Stay inside your module's files.** Only edit paths listed in your module MD §4. The only exceptions are tests that live next to your code and `TILL_NOW.md` (§8). Touching another module's files requires the owner's OK.
3. **Units:** every numeric field and column carries its unit suffix (BACKBONE §5.2). All conversions go through `shared/units.py` / `shared/units.ts`. Do not write inline `* 1000` or `/ 60`.
4. **IDs:** build them with `shared/contracts/ids.py` (`simulation_id`, `incident_id`, `canonical_link_id`, …).
5. **Randomness:** only `numpy.random.Generator(PCG64(seed))`. No `random`, no global `np.random` (BACKBONE §5.4).
6. **Firewall (BACKBONE §11):** inference code only ever receives a `SensorWindow`. Ground truth (`hidden.*`, `LK_*`, hidden node states, `scenarios.*`, challenge spec) never reaches the model, the agent tools or the frontend before reveal. Modules 02, 04 and 08 each have a firewall test, and it must stay green.
7. **No secrets, no hard-coded cloud identifiers.** No account IDs, Bedrock model IDs, container image URIs or API keys in code or docs. Read them from env (`infra/env.sh`, SSM) or discover them (`aws bedrock list-foundation-models`, `sagemaker.image_uris.retrieve`). Mark anything uncertain `<VERIFY: …>` and list it in `docs/RUNBOOK.md` → "Values to confirm before running".
8. **AWS is terminal-driven.** Use `infra/scripts/NN_*.sh` (idempotent, `set -euo pipefail`, tagged `project=aquaagent`, logged to `infra/logs/`). Console clicks only happen at a documented **MANUAL STEP** (Bedrock model access, Amplify↔GitHub OAuth).
9. **Local first (BACKBONE §3.3).** Everything must run with `AQUA_MODE=local` / `docker compose` before it is deployed.
10. **Claims discipline (BACKBONE §16).** Never write a metric you did not measure. Every number in README, slides or reports must trace to `experiments/` or a test output.
11. **Tiers are law (BACKBONE §2, §12).** T1 = the local MVP detection loop. **No T2 work (AWS deploy, SageMaker, localisation, Bedrock) starts before gate MVP passes**, and T2 goes in order T2a → T2b → T2c → T2d. T3 only if T1+T2 are green. A small feature that works beats five that almost work. Respect the cut lines in BACKBONE §13.
12. **Git:** the human manages branches. Do **not** create, switch or delete branches, push, rebase or force anything. Only commit when the human asks you to, and when you do, use their message conventions.
13. **Python 3.12** (`make setup`). WNTR 1.5.0 has no wheels for 3.14.

## 4. Workflow for one step (sub-module)

```
1. Read §1 files. Find your step in module MD §6. Check TILL_NOW.md that its dependencies are done.
2. Restate in 2–3 lines: the step, its "done when" check, files you will touch.
3. Implement. Small, typed, docstrings that cite BACKBONE § numbers. No business logic outside your files.
4. Write/extend tests (module MD §8). Run:
     make lint && make contracts-test && .venv/bin/python -m pytest <your module tests>
5. Run the step's "done when" check. Paste the exact command + output summary in your report.
6. Update TILL_NOW.md (§8 below).
7. STOP. Report: what changed (paths), check output, anything surprising, next step.
   Do not start the next step unless told to.
```

If a "done when" check cannot pass, do not paper over it. Report the real output, propose a fix, and stop.

## 5. Definition of done

| Level | Done when |
|---|---|
| Step | its "done when" check passes, tests are green, and TILL_NOW.md is updated |
| Module | every §6 step is done, and the module MD §9 gate checklist is ticked with evidence (command + output) |
| T1 build | G1–G9 pass. G10 is the demo-readiness gate. |

## 6. When something is wrong or missing in the contract

1. **Stop** the affected work. Don't work around it silently.
2. Check `docs/BACKBONE_ISSUES.md` (resolution log). If the question was already decided, follow BACKBONE as written.
3. If not, add a proposal under **`## 13. Proposed Backbone Changes`** in your module MD (what, why, which contracts, impact) and an OPEN row in `docs/BACKBONE_ISSUES.md`.
4. Tell the human. Only the owner edits BACKBONE.md and bumps `backbone/x.y.z` (BACKBONE §17), and then `shared/contracts/` is updated and `make contracts-test` re-run.

## 7. Quick commands

```bash
make setup                 # Python 3.12 venv (uv) + dev + sim deps (wntr 1.5.0) + .env / infra/env.sh templates
make setup-ml / setup-api  # add ML / API deps when your module needs them
make lint                  # ruff + bash -n on infra scripts
make contracts-test        # BACKBONE examples ↔ Pydantic, TS enum parity, units
make test                  # all Python tests
make help                  # every target (RUNBOOK indexes them)
make status                # AWS resources at a glance
```
Python is `.venv/bin/python`, with the repo root on `PYTHONPATH` (pytest is configured in `pyproject.toml`). The repo path may contain spaces, so always quote paths in shell.

## 8. Updating TILL_NOW.md (required at the end of every step)

Append one row to the **Progress log** table and update the module's row in **Module status**:

```
| 2026-10-08 14:30 | 01 | step 3 "junction + pipe leaks" | done | sim/engine/leaks.py, sim/tests/test_leaks.py | `pytest sim/tests/test_leaks.py` 6 passed | — |
```
Columns: date-time · module · step · status (`done` / `partial` / `blocked`) · files · evidence · notes/decisions. Keep entries factual. No plans, and no claims without evidence.

## 9. Asking vs deciding

Decide yourself when BACKBONE or your module MD already answers the question, or when it is an internal implementation detail inside your files.
Ask the human when the answer would change a contract, touch another module's files, add AWS cost, need a MANUAL STEP, or move a cut line (§13).
