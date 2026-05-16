# PROMPT.md — What's next: Phase C

> This file describes the upcoming phase of work. It is updated whenever a phase ships. Read [CLAUDE.md](CLAUDE.md) first for project orientation.

## Where we are

Phase A (foundation) and Phase B (agents + LangGraph + CLI) are both **merged to `main`**. 101 unit tests pass. The full pipeline runs end-to-end with stubbed LLM. No live Gemini API call has been made yet.

## What Phase C is

**Goal:** Take the merged Phase B pipeline and exercise it on real data through real Gemini API, then polish the rough edges that only surface under real-world conditions.

Phase C is **not** a big-feature phase. It is the "make it actually work on the 5 test companies" phase. Expect: small bug fixes, prompt tuning, observability improvements, cost validation, and a final acceptance run on all 5 companies in `data/inputs/`.

## Phase C deliverables

The following must all be true at the end of Phase C:

1. **All 5 companies in `data/inputs/` (Centum, Connplex Cinemas, Gati, Ind Swift, Kalyani Forge, Ksolves) produce a valid `teaser.pptx` and `citations.docx` from a live Gemini run.** Total cost per teaser ≤ $0.50 on Gemini.
2. **The five polish items from the Phase B final review are addressed** (see "Polish items" below).
3. **A real run produces a well-formed `trace.json`** containing non-zero `total_cost_usd`, per-step entries, and timings. Inspectable for debugging.
4. **Anonymization is verified manually on at least 2 decks** — the real company name does not appear anywhere in the rendered `.pptx`.
5. **A README "Sample outputs" section** links to the 5 generated decks (committed under `data/outputs/_samples/` or similar; keep them small enough to commit).
6. **No live-API tests are added to the pytest suite.** Stubbed tests stay; live runs stay manual.

## Phase C plan (recommended task order)

This is the recommended order. Use the `superpowers:writing-plans` skill to expand into a full per-task plan before executing. **Do not skip the planning step** — Phase C is small but has live-API risk; a written plan keeps cost predictable.

### Stage 1: Polish items (no live API needed)

These are well-specified and can land before any live run. They are listed in detail in the memory file `phase_c_polish_items.md` (loaded automatically). Briefly:

1. **Critic judgment failure visibility** — `agents/critic.py`: when the Flash judgment call raises, append a synthetic `CriticIssue(severity=warning, category="judgment_unavailable", …)` so the report doesn't silently look "all clear."
2. **TraceWriter cost is recorded** — `cli.py`: before `trace.finalize()`, call `trace.add_cost(tracker.total_cost_usd)`. Otherwise every `trace.json` says `total_cost_usd: 0.0`.
3. **Researcher warns on empty Tavily** — `agents/researcher.py`: if no hits across any query, log a warning and write a "web_research_empty" note into the trace step.
4. **Renderer asserts index contiguity** — `render/deck.py`: assert that `[s.index for s in slides]` equals `list(range(len(slides)))`.
5. **(Optional)** Composer sub-call failures escalate — if a planned chart/image is missing in the composed slide, surface a `CriticIssue` warning. Skip if it complicates the Composer significantly.

Each polish item should ship with a test (or a test update) and a small commit. After stage 1: full pytest suite still green, ideally a few new tests.

### Stage 2: First live run (single company)

Pick one company with the smallest data pack (Ksolves's one-pager is the obvious choice). Configure `.env` with real API keys. Run:

```bash
kelp-teaser run data/inputs/Ksolves/
```

Then **manually inspect**:
- The `.pptx` opens in PowerPoint, has 3 slides, branding looks right.
- The real company name "Ksolves" appears **nowhere** in the deck text. Use Find/Replace in PowerPoint to verify.
- Every claim in `citations.docx` has a plausible source_id.
- `trace.json` shows reasonable token counts and total cost ≤ $0.50.

**This is the highest-risk moment in Phase C.** Real Gemini output may not match the strict Pydantic schemas. Common failure modes to look for:
- Composer returns a slide with `index` ≠ requested index → renderer reorders silently.
- Composer hallucinates a `source_id` that doesn't exist in `docs`/`web_snippets` → Critic flags it as blocking. Fix the Composer prompt to enforce stricter source listing.
- Planner picks `hero_image` but `image_brief` is too vague → Pexels returns junk. Tune the planner prompt's examples.
- Cost exceeds the soft warning ($2). Investigate which agent's tokens are blowing up.

Iterate on prompts until Ksolves produces a presentable deck. Each prompt iteration is a tiny commit.

### Stage 3: Remaining 4 companies

Once Ksolves works, run the other four. Expect 1-2 to surface prompt issues that didn't appear in Ksolves (e.g. financials with complex tables, a sector the prompt examples don't cover well). Tune prompts as needed. Commit iteration as you go.

### Stage 4: Sample output capture

Copy each company's final `teaser.pptx` and `citations.docx` into `data/outputs/_samples/` (or similar; create a folder gitignored exceptions). Commit them. Update the README's "Sample outputs" section to link them.

### Stage 5: Closeout

- Run the full pytest suite one final time, confirm 101+ passing.
- Make sure `git status` is clean (no stray run-folders in `data/outputs/` that weren't intended).
- An empty `chore: phase C complete` commit on a branch named `phase-c-live`.
- Merge to `main` via `--no-ff` to keep the phase visible in history.

## Operating instructions for Phase C

- **Use a worktree.** Phase C will iterate on prompts which is messy. Create `../AI-ML-GC-RND-phase-c` on branch `phase-c-live` before starting. Tear down after merge, same pattern as Phase A and B.
- **Each prompt iteration is its own commit.** Don't lump 10 prompt tweaks into one commit.
- **Track live-API spend.** Print and log it after every run. If a single run exceeds $1, stop and investigate — something is wrong.
- **Don't add unit tests for prompt outputs.** Stubbed unit tests are stable; live API tests are flaky and expensive. Manual inspection is the right tool for prompt quality.

## What's NOT in Phase C

Don't do these in Phase C unless the user explicitly asks:

- Adding the Critic revision loop (it's deferred to v3 per spec Section 11).
- Switching to a different LLM provider (Gemini-only at runtime per the spec).
- Building a Web UI (spec non-goal).
- Adding RAG / vector DB (spec non-goal).
- Adding multi-provider fallback (spec non-goal).
- Visible per-claim citation superscripts on slides (deferred to v3).

When in doubt about scope, check spec Section 11 "Deferred to v3."

## Definition of done for Phase C

- [ ] All 5 polish items addressed and tested.
- [ ] All 5 companies produce a teaser deck end-to-end from live Gemini.
- [ ] Per-teaser cost ≤ $0.50.
- [ ] No live test in pytest suite; stubbed tests still pass.
- [ ] Sample outputs committed and linked from README.
- [ ] Phase C merged to `main` via `--no-ff`.

After Phase C, the project is portfolio-ready.
