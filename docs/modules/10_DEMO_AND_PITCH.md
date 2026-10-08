# 10_DEMO_AND_PITCH.md
Backbone version: backbone/1.1.0 | Gate: **G10** | Tier: **T1** | Est. effort: 6 h
Depends on: 08 (deployed stack, reveal logs), 09 (Amplify UI), 04/05/06/07 (measured numbers in `experiments/`), 03 (status/teardown) | Blocks: — | Schedule slot: Day 4 AM (video, slides) · Day 4 PM (rehearsal ×3, freeze 3 h before judging) (BACKBONE §13)

## 1. Purpose
Make the 60-second demo (BACKBONE §1.2) unbreakable and honest. That means a shot-by-shot script, a warm-up checklist, three consecutive clean runs on the deployed stack, and a recorded fallback video. Slides only use numbers traced to `experiments/`, there is a claims-to-avoid list, and judge Q&A is prepared.

## 2. Inputs — contracts consumed
- §1.2 demo promise, §1.3 principles, §16 claims discipline, §9.5 evaluation targets, §13 schedule/cut lines, §14 risks
- Evidence: `experiments/<model_version>/metrics.json`, `hop_error.csv` (04), `experiments/thr_ds1_*/metrics.json` + tables (05), `experiments/<mv>/sagemaker.json` (06), G7 report fixtures (07), `demo/reveal_logs/` (08), manifest §7.6 (02: dataset size, test-sim counts, holdout)
- §7.14.1 `/health`, `/challenge/*` for the live demo; scripts `90_status.sh`, `99_teardown.sh` (03)

## 3. Outputs — contracts produced
- `docs/demo/DEMO_SCRIPT.md` (shot-by-shot), `docs/demo/WARMUP_CHECKLIST.md`, `docs/demo/SLIDES_OUTLINE.md` (every number → `experiments/` path), `docs/demo/QA_PREP.md`, `docs/demo/CLAIMS_TO_AVOID.md`
- `s3://$AQUA_BUCKET/demo/fallback_recording.mp4`, `s3://…/demo/reveal_logs/`
- README "Results" section generated from `experiments/` (no hand-typed numbers)

## 4. Files owned
`docs/demo/` (all), `README.md` §Results (co-owned with the human), `scripts/make_results_table.py` (reads `experiments/` → markdown table).

## 5. Design decisions (binding)
- **Every number on slides, README and narration is traced** to a file in `experiments/` or `demo/reveal_logs/` (§16, G10). The slide outline lists the source path next to each number. *Rejected:* rounding or "approx." claims without a source.
- **Always show alongside our numbers:** dataset size, number of test sims, holdout definition, false-alarm rate (§16).
- **External results** (AquaSentinel, Heter-GATRes from the briefing) are used only as motivation and labelled "their results on their benchmarks" (§16).
- **Fallback-first:** the video is recorded *before* the final rehearsal, and the local `docker compose` stack is ready on the laptop (§14 Wi-Fi Critical).
- **Feature freeze 3 h before judging** (§13). After the freeze only config, warm-up and copy changes are allowed.

## 6. Implementation plan
| # | Step (≤ 2 h) | Done when |
|---|---|---|
| 1 | `DEMO_SCRIPT.md`: the §1.2 flow as shots (see skeleton below) with timings, what to click, what to say, and the fallback line for each shot. | Script fits in 60 s in a dry run against mock mode (09). |
| 2 | `WARMUP_CHECKLIST.md`: `make status`; `/api/health` ok; (T2b) one warm `invoke-endpoint`; one diagnose (template; T2d Bedrock if shipped); session reset; browser zoom; phone hotspot ready; local compose ready. | Checklist executed once end-to-end, logged in TILL_NOW. |
| 3 | Three consecutive clean challenge runs on the deployed stack (`api/scripts/e2e_challenge.py --base $API_URL` + one through the UI); save reveal logs to S3. | **G10 part 1:** 3/3 clean, reveal logs in `s3://…/demo/reveal_logs/`. |
| 4 | Record the fallback video (screen + narration) of a clean run; upload. | `aws s3 ls s3://$AQUA_BUCKET/demo/fallback_recording.mp4` exists. |
| 5 | `scripts/make_results_table.py` → README Results + `SLIDES_OUTLINE.md` with source paths. | Every number in README/slides has a path; a grep for digits in the slide outline shows a source next to each. |
| 6 | `CLAIMS_TO_AVOID.md` + `QA_PREP.md`; rehearsal ×3 with a timer; freeze. | Rehearsal times recorded; freeze timestamp in TILL_NOW. |
| 7 | After judging: `infra/scripts/99_teardown.sh --endpoint-only`; later the full teardown (03). | `make status` shows the endpoint absent. |

### Shot list skeleton (BACKBONE §1.2)
| t (s) | Shot | Click / action | Say (no unmeasured numbers) | Fallback |
|---|---|---|---|---|
| 0–8 | Healthy network, live WNTR physics, flow animating | Play at 5× | "Every pressure and flow here is solved by WNTR, a hydraulic physics engine. The UI computes nothing." | Video 0:00 |
| 8–16 | Judge opens a tap | Tap T2 → OPEN | "Real demand change → real pressure response." | Video 0:08 |
| 16–22 | TEST THE AI | Click, medium | "The backend secretly injects a real leak. The AI sees only S1–S3 and F1–F2." | Video 0:16 |
| 22–35 | Detection | Wait for DETECTED | "A model trained only on normal behaviour predicts each sensor from the others; the residuals cross a dual threshold." (T2b: "served by SageMaker") | Video 0:22 |
| 35–48 | AquaAgent report | Report panel | "AquaAgent explains what changed, why it is suspicious, the evidence and an action. Every number comes from the measured residuals. [template label / T2d: Bedrock + grounding badge]" | Video 0:35 |
| 48–60 | REVEAL | Click REVEAL | "Ground truth vs AI: where the leak really was, and how fast we detected it, from this run." (T2c: + rank of the true pipe) | Video 0:48 |

### Claims to avoid (§16) and say instead
Never say: "we solve leakage", "detects every leak", "three sensors are enough for any network", "represents Pune", "real-time city telemetry", "AWS makes it accurate", "100% accuracy" (unless our table says so, with n). Say: "in our simulated network", "we evaluate", "under these assumptions", "probable zone", "the prototype demonstrates".

### Judge Q&A prep (answers must cite `experiments/`)
- **Why MLP vs GNN?** D4: we ship whichever wins on val hidden-node MAE (show both numbers if the GNN was tried). On a fixed 8-node graph an MLP can match a GNN, and a GNN earns its place on unseen topologies (T3, §9.1).
- **How do you avoid "pressure↓ = leak"?** Operational-variation scenarios (HIGH/LOW demand, demand shift) are in training and val. The predictor reconstructs *normal* behaviour including those, and the FAR on them is reported separately (BI-06, §9.3).
- **Why does the model not just learn the leak?** Normal-only training (§9.1), the residual sanity test (04), and LOO residuals at observed sensors (§9.2).
- **What does synthetic data not prove?** Real-sensor noise and drift, model mismatch (roughness, demand uncertainty), larger networks, and real false-alarm costs. Ours is one small network, simulated (§16).
- **How is the LLM prevented from making things up?** JSON-only tools, a forced `submit_report`, the grounding check with retry, and a template fallback (§9.6). Show the badge.
- **How does it localise unseen leak locations?** Physics signatures include the holdout locations, and holdout top-3 is reported separately (§8.5, §9.4).
- **Cost/scale?** Endpoint deleted after judging. Bedrock/Agents/Step Functions/IoT are "next steps" (§2.1 T3).

## 7. AWS steps
```bash
make status                                                           # warm-up: every row present
curl -s -H "X-Api-Key: $KEY" "$(cat infra/.state/api_url)/api/health" # ok / ok / ok
aws sagemaker-runtime invoke-endpoint --endpoint-name aquaagent-predictor --content-type application/json \
  --body fileb://req.json /dev/stdout                                  # warm the endpoint (req from 13's smoke)
aws s3 cp demo.mp4 s3://$AQUA_BUCKET/demo/fallback_recording.mp4
aws s3 sync demo/reveal_logs s3://$AQUA_BUCKET/demo/reveal_logs/
infra/scripts/99_teardown.sh --endpoint-only                          # AFTER judging
```

## 8. Tests
- **Traceability test:** `scripts/make_results_table.py --check` fails if README Results differs from what `experiments/` produces.
- **Claims lint:** `grep -RinE "solve leakage|every leak|100% accura|represents pune|real-time city" README.md docs/demo` → no hits (unless quoted in CLAIMS_TO_AVOID).
- **Demo run log:** 3 reveal logs with `detected=true` and timestamps within one session window (G10).
- **Firewall:** n/a (verified in 08). The demo never shows the dev console or the network tab during a challenge.

## 9. Acceptance gate — G10
Copied from BACKBONE §12, plus module checks:
- [ ] 3 consecutive clean challenge runs on the deployed stack
- [ ] recorded fallback video in `s3://…/demo/`
- [ ] every number on slides traced to `experiments/`
- [ ] (module) warm-up checklist executed and logged
- [ ] (module) dataset size, test-sim count, holdout and FAR shown with every metric
- [ ] (module) endpoint deleted after judging

## 10. Risks and fallbacks
- Venue Wi-Fi fails (§14 Critical): fallback video + local compose stack + phone hotspot.
- Endpoint cold or latency (§14): warm-up call; real-time endpoint.
- Agent not grounded live: template label (cut line, evening Day 3).
- Overclaiming (§14): the claims lint + traceability test.
- Flaky challenge (no detection at small size): demo uses `medium`; `small` only if measured recall supports it.

## 11. Handoff
- To the human/judges: deployed URL, video, slides, `docs/demo/*`, `make status`, teardown commands.
- To post-event: `99_teardown.sh` (endpoint-only, then full), S3 kept as evidence.

## 12. Agent prompt
```
You are implementing module 10 (Demo and Pitch) of AquaAgent.
Read, in order and completely: INSTRUCTIONS.md, BACKBONE.md (especially §1, §13, §14, §16),
docs/modules/10_DEMO_AND_PITCH.md, TILL_NOW.md. Read nothing else for context; take numbers ONLY from files
under experiments/ and demo/reveal_logs/ (local or S3) — cite the path for every number you write.
Implement §6 in order; after each step run its "done when" check, update TILL_NOW.md, STOP.
Only edit files in §4. Never write a claim from the "never say" list; never invent or round a metric without
its source. If a required number does not exist yet, write TODO(<source path>) instead of a value.
If a contract is wrong, write it under §13 and stop. Do not create git branches or push.
```

## 13. Proposed Backbone Changes
_(empty)_
