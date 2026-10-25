# AI Excel Copilot

Upload your Excel. Understand your data.

## Phase 1 — Foundation (this repo state)

Auth, private upload, storage, database, job queue, and a worker that safely validates each file.

```
supabase/migrations/0001_init.sql   tables, RLS, queue function, private bucket
worker/                             FastAPI + polling worker (Python)
web/                                Next.js upload UI (login, upload, file list)
docker-compose.yml                  runs the worker
```

### Setup

1. **Supabase project** (free tier). In the SQL editor, run `supabase/migrations/0001_init.sql`.
   In Authentication settings, enable email sign-in (turn off "Confirm email" while developing if you want).
2. **Worker**
   ```bash
   cp .env.example .env        # fill SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY
   docker compose up -d --build
   curl http://127.0.0.1:8000/health
   ```
   Without Docker: `cd worker && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt && uvicorn app.main:app`
3. **Web**
   ```bash
   cd web
   cp .env.local.example .env.local   # fill URL + anon key (public)
   npm install && npm run dev
   ```
4. **Tests**: `cd worker && pytest`

### How a file flows

1. Browser uploads to `workbooks/<user_id>/<workbook_id>/original.xlsx` (private bucket, folder-per-user policy).
2. Browser inserts a `workbooks` row. A DB trigger creates an `analysis_jobs` row.
3. Worker calls `claim_next_job()` (`FOR UPDATE SKIP LOCKED`), downloads the file, computes SHA-256, and validates:
   zip structure and size limits, no macros, real workbook, readable by openpyxl.
4. Worker sets the workbook to `validated` (sheet count, hidden sheets, external links flag) or `rejected` with a user-readable reason.
   Unexpected errors retry up to 3 times, and jobs stuck as `running` are reclaimed after 10 minutes.

### Security properties in place

- Service-role key lives only in the worker; the browser has the anon key and RLS.
- A user can only read, insert or delete their own rows and files; storage path must start with their user id (DB check constraint).
- The original file is never modified. Macros are rejected, external links are flagged but never followed.
- Logs contain ids and error types only, never filenames or cell contents.
- Users can delete a file (storage object and row) from the UI.

### Done when (Phase 1)

- [ ] Sign up and sign in work
- [ ] Uploading a valid .xlsx shows "Ready · N sheets"
- [ ] A .xlsm, a renamed .txt, or a corrupted file shows a clear rejection reason
- [ ] Two users cannot see each other's files
- [ ] Delete removes the file and row
- [ ] `pytest` passes

## Phase 2 — Excel engine (report §4, §10, §13, §14 phases B–D)

After validation, the worker turns every sheet into a **profile**. It is deterministic: no LLM, and every
number comes from code and carries the Excel rows it came from.

```
worker/app/engine/
  parse.py      workbook -> sheets, cached values, formulas, merged cells, Excel tables, error cells
  tables.py     find the real tables: skip titles/notes, find the header, drop TOTAL rows, join split blocks
  values.py     cell classification (FR/EN/AR): "1 234,50 DA", "15 %", dd/mm/yyyy, "5 août 2026", placeholders
  columns.py    type detection (integer, decimal, currency, percentage, date, boolean, text) + currency/unit
  stats.py      distributions, cardinality, outliers (3×IQR; log scale for money)
  roles.py      measure / dimension / time / identifier / free text, with a confidence for each guess
  quality.py    data-quality findings (§10), each worded "potential issue" with the affected rows
  formulas.py   formula-derived vs typed values, inconsistent formulas in a column
  analyze.py    orchestrator + relationships between tables + summary
worker/app/persist.py   writes the profile to Postgres and the cleaned tables (Parquet) to Storage
supabase/migrations/0002_profile.sql   sheets, data_tables, column_profiles, findings, workbook_profiles, 'artifacts' bucket
web/src/app/workbooks/[id]             read-only "Data profile" page
```

### Upgrade from Phase 1

1. Run `supabase/migrations/0002_profile.sql` in the SQL editor. It also re-queues files you already uploaded, so they get profiled.
2. Rebuild the worker: `docker compose up -d --build`.
3. Redeploy the web app. A file now goes `Checking → Analyzing → Ready`, and "View profile" appears.

### What the engine detects

- **Tables**: several per sheet, title/notes above the header, blank rows inside a table, total rows, Excel-defined tables.
- **Types and roles** per column, with confidence. Text numbers, French decimals, DA/DZD, percentages, text dates, Arabic headers.
- **Findings**: missing values, duplicate rows and ids, inconsistent spelling/casing, near-duplicate labels, mixed or ambiguous date formats,
  invalid values, unexpected negatives/zeros, extreme outliers, Excel error cells, inconsistent formulas, typed values among formulas,
  hidden/empty sheets, external links.
- **Relationships** between tables (e.g. `Sales.wilaya` → `Lookup.wilaya`).

### Decisions worth knowing

- Ambiguous dates (`03/04/2026`) are read day/month. If a column contains dates that can only be month/day, it is flagged (high severity when both orders appear).
- Outliers use 3×IQR fences, on a log scale for heavily skewed positive columns, so normal long tails in money columns are not flagged as errors.
- Limits (env vars): 2M cells, 200k rows per table, 120 s per analysis. Over the limit the file is rejected with a clear message or truncated with a finding.
- Domain inference ("this looks like a sales file") is not here: the report places it in the AI layer (Phase 5). Phase 2 provides the facts it will use.

### Tests

`cd worker && pytest` — 88 tests, including a benchmark of expected interpretations (report §22): the two fixture workbooks,
two tables on one sheet, titles without a blank row, text numbers, Excel tables, conflicting dates, Arabic headers, error cells,
formula slips, and the safety limits.

### Done when (Phase 2)

- [ ] `01_sales_clean.xlsx` → 3 tables, correct types/roles, only a "hidden sheet" note, link Sales → Lookup
- [ ] `02_messy_ventes_fr.xlsx` → header on row 4, TOTAL row left out, and findings for missing values, duplicate row, wilaya spelling, mixed dates, large outlier
- [ ] `03_blank_row_inside_table.xlsx` → one table, 1 blank row noted
- [ ] Deleting a file removes the file, the profile, and the cleaned tables
- [ ] `pytest` passes

## Phase 3 — Analytics (report §6.1, §14 phases F–H)

The worker now computes **facts** from the cleaned tables: totals, averages, rankings, trends, changes, associations,
targets, and unusual values. Facts are what the AI layer (Phase 5) and the charts (Phase 4) will build on.
The principle from the report holds: code computes, the LLM only phrases, nothing is stated that was not recomputed.

```
worker/app/analytics/
  plan.py             which columns can be summed, ranked, or plotted over time; reliability from caveats
  periods.py          time grain choice + "complete period" logic (an unfinished month is not a decline)
  facts_basic.py      key figures (KPIs), rankings by category, unusual values
  facts_time.py       trends, change vs previous period, largest swing, unusual periods, breakdown over time
  facts_relations.py  associations, derived columns (total = qty × price), actual vs target
  verify.py           independent re-computation in plain Python: a fact is kept only if it matches
  run.py              generate -> score (usefulness × reliability) -> keep the best per group -> verify
supabase/migrations/0003_facts.sql   facts table (+ re-runs already profiled files)
web/src/components/FactsSection.tsx  "Key figures and patterns", each fact inspectable
```

### Upgrade from Phase 2

1. Run `supabase/migrations/0003_facts.sql` in the SQL editor. It re-queues profiled files so they get their facts.
2. Rebuild the worker (`docker compose up -d --build`) and redeploy the web app.

### Rules the engine follows (so the numbers can be trusted)

- **Prices and rates are averaged, never summed.** Only amounts and quantities get totals.
- **Incomplete periods are left out of comparisons**, and the fact says so. A period counts as complete when the data
  reaches within 20% of its boundary.
- **A "change" needs at least 5 rows behind each period.** Thin series get a caveat instead of a headline like "+567%".
- **Columns computed from others** (total = quantity × price) are detected, reported with the rows that break the rule,
  and never reported as a "correlation".
- **Associations are worded as such**, never as causes. Headlines never use causal wording (tested).
- **Caveats come from the Phase 2 findings** (duplicates, missing values, extreme values, mixed date formats)
  and lower the reliability score by a named amount.
- **Every fact stores its definition, source rows and a `spec`** that is enough to recompute it. The same `spec`
  will drive drill-down and questions later.
- **Analytics can never break a profile**: if it fails, the profile stays usable and the failure is recorded.

### Done when (Phase 3)

- [ ] `01_sales_clean.xlsx`: total_dzd 7,196,350 DZD; 9 months; September vs August +71%; target reached 53%; "total = quantity × unit price in every row"
- [ ] `02_messy_ventes_fr.xlsx`: the 9,999,999 row appears as an unusual value **and** as the one row where total ≠ quantity × price; caveats mention the duplicate and the missing values; no "change" claims on thin weekly data
- [ ] Opening a fact shows its definition, caveats, the numbers, and "recomputed independently and matched"
- [ ] Deleting a file removes its facts
- [ ] `pytest` passes (77 tests)

## Phase 4 — Visualization (report §5, §11, §13 "Visualization", §14 phases F–G, I–J)

Charts are not decorated numbers: each one is chosen by rules from the detected structure, scored, and traceable to verified facts.
Titles are the analytical question; every chart says why it exists; every bar, point or month opens the rows behind it.

```
worker/app/charts/
  build.py     facts -> candidate chart specs (the §5 mapping: line for time, bars for rankings, stacked for category × time,
               scatter for associations, histogram for distribution, actual-vs-target); donut offered as a switch, never the default
  select.py    scoring (usefulness × reliability × readability) and a varied first screen: 4 KPI cards, 1 primary, ≤4 secondary,
               the rest under Explore. Redundancy penalties: same chart type, same question, same category again.
supabase/migrations/0004_charts.sql     charts table (+ re-runs profiled files)
web/src/lib/dataEngine.ts   filters, aggregation, drill-down in the browser, mirroring the Python rules exactly
web/src/lib/chartOption.ts  spec -> ECharts option (pure, escaped tooltips, dashed incomplete periods)
web/src/components/         Dashboard, KpiCard, ChartCard, FilterBar, DrillPanel, WorkbookView (Overview / Explore / Details)
```

### Upgrade from Phase 3

1. Run `supabase/migrations/0004_charts.sql`. It re-queues profiled files so they get charts, and so their cleaned tables
   are rewritten in the format the browser reads (snappy Parquet, millisecond timestamps).
2. `npm install` in `web/` (adds `echarts`, `hyparquet`), rebuild the worker, redeploy the web app.

### How filters and drill-down work (no new server)

The first screen is drawn from the stored specs, so it opens instantly. When you apply a filter or click a bar, the browser
downloads the cleaned table once (Parquet, ~16 KB per 340 rows), filters it, and re-runs each chart's `query`.
Charts that cannot be recomputed in the browser (targets) say "Not affected by filters".
A date filter that cuts a month marks that month as incomplete, exactly as the worker would.

### Tests (what proves it)

- `cd worker && pytest` — 88 tests, including chart-spec rules: first screen size and variety, titles are questions,
  chart numbers equal the verified fact numbers, bars sorted, donut only offered for 2–5 additive groups, partial periods flagged.
- `cd web && npm test` — 40 tests:
  - **Parity** with Python/pandas for 5 filter combinations and every period grain (day, week, month, quarter, year),
    drill-down rows, and scatter sampling. I broke the engine on purpose twice to confirm these tests fail when they should.
  - **Renderers** for every chart kind the worker can produce, and tooltip HTML escaping of spreadsheet text.
  - **The dashboard itself** (rendered with the real sales specs): KPI values, filtering to one category and clearing it, date ranges,
    "no rows match", drill-down to the exact rows, "filter the dashboard to this", Explore grouping.
- Regenerate the golden data after changing worker logic: `cd worker && python scripts/export_golden.py`.

### Done when (Phase 4)

- [ ] `01_sales_clean.xlsx` → Overview: 4 KPI cards (total 7,196,350 DZD with +71% vs August, 53% of target…), a monthly trend,
      the target chart, two rankings, one unit-based chart
- [ ] Filter to one category: KPIs and charts change; "Showing N of 339 rows"; Clear filters restores them
- [ ] Click a bar: the panel lists exactly its rows with Excel row numbers; "Filter the dashboard to this" works
- [ ] A ranking with 4 categories offers a Bars / Donut switch; one with 10 categories does not
- [ ] Explore groups charts (Trends, Regions, Products…); Details still shows the profile, figures and issues
- [ ] Both test suites pass

## Phase 5 — AI layer (report §4.3, §6, §8, §12.4, §15, §22)

The AI is a **phrasing and question-understanding** component, never a calculator. It receives structured facts and a column list,
never rows. Everything it writes is checked against the verified facts, and anything that fails is replaced by built-in text.
**All of it works with no AI at all**; AI is opt-in per user.

```
worker/app/ai/        llm.py      Gemini + any OpenAI-compatible provider (Groq, OpenRouter...); JSON in/out, retries, no content logging
                      claims.py   the validator: every number, period, name, cause and direction in AI text is checked against the evidence
worker/app/context/   infer.py    "About this workbook" (§4.3): domain guess with evidence, entities, time span, assumptions, uncertainty
worker/app/insights/  build.py    "What stands out" (§6): built-in text from facts; AI wording only when it validates
worker/app/qa/        schema, plan  question -> restricted JSON plan -> validation (names, types, values; prices are never summed)
                      execute     runs the plan with pandas (agg, group, series, compare, contribution, top_rows)
                      verify      recomputes the result a second way in plain Python; unverifiable answers are not shown
                      rules       built-in planner for common questions (EN/FR), asks when ambiguous instead of guessing
                      answer, run wording (template, or AI text if it validates) and orchestration, with fallbacks at every step
worker/app/questions.py           answers queued questions (Postgres is the queue; no server to expose)
supabase/migrations/0005_ai.sql   user_settings (consent), insights, questions (+ rate limit 60/hour), request_reanalysis()
web/src/components/               AboutCard, InsightsPanel, AskPanel, AiConsent; Overview gets context + insights; new Ask tab
worker/scripts/eval_ai.py         measures YOUR provider inside the guard rails (§22)
```

### Upgrade from Phase 4

1. Run `supabase/migrations/0005_ai.sql`. It re-queues files so they get their context and built-in insights.
2. `docker compose up -d --build` (the compose/Dockerfile in this zip match the hardened version that worked for you).
3. Redeploy the web app. The **Ask** tab works immediately, with built-in logic.

### Turning AI on (optional)

In `.env` (see `.env.example`):
```
AI_PROVIDER=groq            # none | gemini | groq | openai_compatible
AI_API_KEY=...
AI_MODEL=...                # no default on purpose: model names change often, so use one your provider currently lists
```
Advanced (optional, add only if needed): `AI_BASE_URL=` for `openai_compatible` providers, `AI_REASONING_EFFORT=low` for reasoning models that run out of tokens (such as `openai/gpt-oss-20b` on Groq), and `AI_PHRASE_ANSWERS=true` to also let the AI reword answers. **Answer wording by AI is off by default**: measured with a real provider it added nothing over the built-in wording and doubled the calls. The AI's value is understanding questions. Keep comments on their own lines in `.env`, not after a value.
Then each user switches it on under **Ask → AI assistance**. Before enabling, **read your provider's current data terms**.
When this was written, sources disagreed on Groq's retention guarantees, and Google's Gemini free tier may use inputs to improve
its products (human reviewers may read them); a paid tier or a provider with a no-training policy is the safer choice for customer data.

### What leaves the server, and what never does

- **Sent:** the question, column names, non-personal category labels, and figures already computed (totals, rankings, changes).
- **Never sent:** rows, identifiers, **people's names** (facts and values about person columns stay on the server), free text, the file.
- Facts about people are worded by built-in text only. Prompts and answers are never logged (only ids and error types).
- The AI cannot run anything: its only output is a JSON plan that must pass validation. Hostile or hallucinated plans
  (unknown columns, `run_sql`, filters on values that don't exist, prompt injection through labels) are rejected and the built-in logic answers.

### Rules the layer enforces (and tests prove)

- **A "why" question gets a contribution analysis**: where the change happened (which category added or removed how much),
  stated explicitly as "not why". Insights separate *what the data shows* / *a hedged possibility* (no numbers, no causes) / *what to check next*.
- **A claim must be traceable.** Numbers must match the evidence in any honest format (7,196,350 / 7.2M / 71%), invented or computed numbers
  are rejected, as are unknown periods and unknown names, causal wording, and a direction that contradicts the data.
- **Degrades, never breaks**: provider error, rate limit, malformed JSON, rejected plan, or rejected wording each fall back to the built-in logic,
  and a provider that failed is not called again for that question.
- **Ambiguity is asked, not guessed** ("Which number do you mean?"). Unanswerable questions get answerable suggestions.
- Every answer shows its calculation, rows used, caveats, and who did what (AI or built-in logic, for the plan and for the wording).

### Tests

- `cd worker && pip install -r requirements-dev.txt && pytest` — **264 tests**, including the claim validator against typical LLM failures,
  provider clients on a mock transport (retries, 429, malformed output, key never in a URL), plan validation, execution + independent verification,
  hostile plans, and end-to-end flows on an in-memory database (consent, queue, ownership, cache).
- `cd web && npm test` — **68 tests**, including the new screens rendered with real worker output.
- **Not tested here:** live calls to a provider (there is no key in the build environment). Run `python scripts/eval_ai.py` with your key; it reports
  how often the AI's plans validate, how often its wording is accepted, and checks that final answers always equal the built-in result.

### Known limits

- Questions outside the six operations are declined (for example "which month had the biggest drop", forecasts, formulas). The next phase adds guided analysis.
- The built-in planner understands common English and French phrasing; unusual phrasing needs AI on.
- Free-tier limits and model names change: expect to adjust `AI_MODEL`, and the worker falls back to built-in logic while a provider is rate-limited.

### Done when (Phase 5)

- [ ] **Overview** shows "About this workbook" (sales, evidence columns, 2026-01-04 to 2026-09-27, assumptions) and "What stands out" (target 53%, +71% change, Electronics 73%…)
- [ ] **Ask** works with AI off: "What is the total sales?", "Which wilaya has the highest sales for Electronics?", "Why did sales increase in September?", "show the largest orders"
- [ ] The "why" answer says where the change happened and ends with "not why"; "what is the weather like?" is declined with suggestions
- [ ] Clicking an insight's next check, or a suggested question, answers without AI
- [ ] AI card is **off by default**, states what is and isn't sent; with a provider configured and AI on, typed questions in your own words work and show "Question understood by AI, then checked"
- [ ] `python scripts/eval_ai.py` reports 100% "final answer correct"
- [ ] Both test suites pass

## Phase 6 — Guided analysis (report §7, §8, §6.3)

**Guide Me** walks a user through what matters in the workbook, in the order the report describes: the big picture, where it comes from,
how it changed, what looks unusual, then what to look at next. Any step can be skipped, and every button runs inside the step.
It is **deterministic**: built from verified facts and the charts already computed, with no AI. (Phase 5's evaluation showed AI wording added
nothing, so there is none here.)

```
worker/app/guide/build.py   the path: overview -> sources -> change -> unusual -> target -> quality -> next (only steps the data supports)
worker/app/qa/highlights.py "What should I pay attention to?" / "Find suspicious data", answered from the stored insights
supabase/migrations/0006_guide.sql   workbook_profiles.guide (+ re-runs profiled files)
web/src/components/GuidePanel.tsx    stepper, narrative, caveats, evidence charts, buttons that run in place, results
```

### Upgrade from Phase 5

1. Run `supabase/migrations/0006_guide.sql`.
2. `docker compose up -d --build`, then redeploy the web app.
3. Open a workbook: the Overview now has a **Walk me through it** button and there is a **Guide** tab.

### How the tour works

- **The path adapts.** A table with no dates gets no "over time" or "unusual month" steps; no target column means no target step; a data-quality step
  appears only when there are real issues. Nothing is invented to fill a step.
- **Every button is a ready, validated plan** ("Explore Online", "What contributed to 2026-04 → 2026-05?", "Inspect transactions in 2026-05"), run by the same
  Ask engine, verified a second way, and shown inside the step. Tests run every button of every guide.
- **Honest wording (§6.3).** The unusual step ends "These are patterns to check, not conclusions." Narratives are built from fact headlines, so every number
  and period is traceable (tested with the claim validator), and none uses causal wording. Each step shows the caveats of the facts it is built on
  (for example "one unusually extreme value", so a 99% share is not presented without context).
- **"What should I pay attention to?" and "Find suspicious data"** (EN/FR) now work in Ask. They list only what the insights already verified, say "patterns, not
  explanations", and say plainly when nothing stands out. A next question that several findings share is offered once, not repeated.

### Tests

- `cd worker && pytest` — **264 tests** (new: path order and adaptation, every button runs and verifies, period filters return the right rows, traceable non-causal narratives,
  attention questions, pipeline isolation).
- `cd web && npm test` — **68 tests** (new: the real tour rendered, back/next, skipping to any step, buttons running in place with progress then result, follow-ups inside a step,
  per-step results, rate-limit message, highlights).

### Known limits

- The tour covers the main table of the workbook (the largest with measures). Other tables are reachable in Explore and Ask.
- The path order is fixed (it follows the report's example); which opportunities fill the "unusual" step is chosen by score.
- Usage measurement (the report's "% of users who click a guided recommendation") is not collected yet; it belongs with monitoring in Phase 8.

### Done when (Phase 6)

- [ ] **Overview** shows "Walk me through it"; the **Guide** tab opens on "Let's understand the big picture" with the KPI cards
- [ ] Steps: big picture → where it comes from (Online 49%) → how it changed (+58%, September +71%) → something unusual (largest change, with "not conclusions") → on track (53% of target) → where to go next
- [ ] You can jump to any step from the list; Back and Next work; Finish returns to the Overview
- [ ] "Inspect transactions in 2026-05" runs inside the step and shows rows from May with Excel row numbers
- [ ] On the messy file: a data-quality step, and a caveat about the extreme value under "where it comes from"
- [ ] In Ask: "What should I pay attention to?" and "Find suspicious data" give short lists with next steps, no repeated suggestions
- [ ] Both test suites pass

## Next: Phase 7 — Export
A PDF report of the dashboard, insights and the guided findings, with the same caveats and definitions, plus optional sharing.

### Phase 7 status

The workbook header now provides **Download PDF**. It downloads a compact, visual PDF
directly in the browser containing:

- workbook context, assumptions, and row/table coverage;
- KPI cards;
- up to three important charts rendered as PDF visuals;
- the three highest-priority grounded insights; and
- only the most relevant caveats and next steps.

No workbook rows or new calculations are sent to a server. The PDF is assembled from the
already-loaded, access-controlled analysis output. The browser downloads it as a PDF file.
Sharing remains intentionally deferred because private workbook authorization
must not be bypassed by public report links.

## Phase 8 — Hardening

Phase 8 adds operational safeguards without exposing workbook contents:

- upload quotas: 25 workbooks per user in 30 days and 10 uploads per day;
- bounded workbook filenames with control characters rejected;
- a user-visible audit trail for upload registration and deletion;
- service-role audit retention cleanup (`purge_old_audit_events`, default 180 days);
- worker health metrics for uptime, completed jobs/questions, and errors;
- explicit UI messages for quota/rate-limit failures and delete failures.

Run `supabase/migrations/0007_hardening.sql` after the Phase 7 migrations. Schedule
`purge_old_audit_events()` from a trusted maintenance job; it is not callable by browser users.
