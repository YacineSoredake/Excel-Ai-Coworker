AI EXCEL COPILOT
Complete Product & Technical Plan
An AI-powered application that understands Excel files, automatically builds meaningful
visualizations, explains the data, detects problems, and guides users through analysis.
Core promise: Upload your Excel. Understand your data.
Product loop: Upload → Understand → Visualize → Explain → Investigate → Act.
Document scope: product vision, user experience, feature set, AI/data pipeline, architecture, security,
roadmap, monetization, implementation strategy, and future expansion.
AI Excel Copilot — Product & Technical Plan Page 1

1. Product Vision
The product is not simply an Excel chart generator. Its central job is to make spreadsheets understandable
to people who may not be data analysts or Excel experts.
A user uploads an .xlsx or .xls file. The system inspects its sheets, headers, values, formulas, dates,
categories, relationships, and data quality. It then infers the likely purpose of the workbook, selects
appropriate visualizations, produces plain-language insights, highlights anomalies and missing data, and
creates a guided path for further investigation.
Positioning: “Your Excel file, explained.” / “Drop your Excel. Understand your data.”
Important differentiation: the AI decides what is useful from the structure and context of the workbook
instead of forcing every workbook into the same dashboard template.
1.1 Product principles
l Context first: understand the workbook before generating charts.
l Useful over decorative: every visualization should answer a meaningful question.
l Explain everything: users should understand why a chart or insight exists.
l Guide, don't overwhelm: surface the next useful question instead of dumping dozens of charts.
l Ground AI in data: numerical claims must be traceable to the uploaded workbook.
l Respect user control: users can inspect, correct, regenerate, filter, and export results.
l Beginner-friendly: no knowledge of SQL, statistics, BI tools, or advanced Excel should be required.
2. Target Users & Use Cases
User Typical problem Product value
Small business Has sales/expenses in Excel but does Automatic KPIs, trends, problems, and
owner not know what matters. explanations.
Employee / office Receives complex spreadsheets and Plain-language workbook summary and
worker needs to understand them quickly. guided analysis.
Manager Needs a quick performance Dashboard + insights + drill-down
overview. questions.
Student Has data but struggles with Explained charts, patterns, and beginner
analysis/visualization. guidance.
Accountant / Works with repetitive financial Anomaly checks, categories, trends,
finance user spreadsheets. summaries.
Sales team Tracks sales by product, person, Performance analysis and comparisons.
region, date.
Inventory Tracks stock and movement. Low-stock, dead-stock, fast-moving and
manager value analysis.
3. Core User Journey
AI Excel Copilot — Product & Technical Plan Page 2

Step 1 — Upload
User drags an Excel file into the application.
Step 2 — Inspect
System reads workbook metadata, sheets, tables, formulas, merged cells, headers, types, dates, blanks,
duplicates, and relationships.
Step 3 — Understand
AI/data engine creates a structured profile of what the workbook appears to represent.
Step 4 — Generate
System chooses KPIs, charts, tables, warnings, and suggested questions.
Step 5 — Explain
AI writes grounded insights using the computed data.
Step 6 — Guide
The interface presents a recommended sequence of investigations.
Step 7 — Ask
User asks natural-language questions about the workbook.
Step 8 — Export / Share
User exports charts/report/dashboard or shares an analysis.
Example: a file called ventes_2026.xlsx may be identified as a sales report with 4,281 transactions,
products, sales representatives, Wilayas, dates, quantities, prices, and revenue. The application can then
produce revenue trends, product performance, regional performance, salesperson performance,
data-quality alerts, and suggested questions.
4. Workbook Understanding Engine
4.1 File ingestion
l Accept .xlsx initially; support .xls where practical.
l Detect workbook name, file size, number of sheets, hidden sheets, sheet dimensions and used ranges.
l Read cell values, formulas, formatting cues, merged cells, tables, named ranges and hyperlinks where
relevant.
l Preserve a safe original copy for audit/reprocessing.
l Do not send the entire raw workbook to an LLM by default.
4.2 Schema and semantic profiling
Convert the workbook into a structured intermediate representation. For each column, detect:
l Data type: text, integer, decimal, currency, percentage, date/time, boolean, identifier.
l Role: dimension, measure, identifier, date/time dimension, category, status, location, person, product,
etc.
l Cardinality and uniqueness.
l Null/missing rate.
l Min/max, distribution summaries and outliers where statistically appropriate.
l Likely currency and units.
l Potential relationships between columns and sheets.
AI Excel Copilot — Product & Technical Plan Page 3

l Formula-derived vs manually entered values.
4.3 Workbook context inference
The system should infer a probable domain such as sales, HR, finance, inventory, project management,
marketing, education, operations, or a generic tabular dataset. The inference should remain probabilistic
and transparent when confidence is low.
Output example:
FILE UNDERSTANDING
Purpose: Sales / business performance
Rows: 4,281
Entities: Products, customers, sales representatives, Wilayas
Measures: Revenue, quantity, unit price
Time dimension: January–September 2026
Potential analyses: Revenue trends, product performance, regional performance, salesperson performance, monthly
comparison.
5. Automatic Visualization Engine
The visualization engine should not simply generate random charts. It should map detected analytical
questions to chart types and rank candidate visualizations by usefulness.
Detected structure Possible visualization
Date + numeric measure Line chart / trend
Category + numeric measure Bar chart
Few categories forming a meaningful Pie/donut when appropriate
whole
Two numeric variables Scatter plot
Category + time + measure Grouped/stacked bars or lines
Geographic/Wilaya field Regional comparison / map in a later version
Ranking Horizontal bar chart
Budget vs actual Comparison bars / variance visualization
Inventory quantity + threshold Stock status / warning visualization
Visualization selection rules
l Prefer a small number of high-value visualizations on the first screen.
l Avoid pie charts when there are many categories or when precise ranking matters.
l Use line charts for ordered time trends.
l Use bars for category comparisons and rankings.
l Use scatter plots for numeric relationships.
l Always include titles that communicate the analytical question, not generic labels such as “Chart 1.”
l Allow users to inspect the underlying rows contributing to a result.
AI Excel Copilot — Product & Technical Plan Page 4

l Allow regeneration when the user changes filters or asks a different question.
6. AI Insights Engine
The AI layer should be grounded in computed statistics rather than being allowed to invent conclusions
from a raw spreadsheet prompt.
6.1 Insight pipeline
l Data engine computes candidate facts: totals, changes, rankings, distributions, correlations,
missingness, anomalies, etc.
l A deterministic/analytical layer validates the facts.
l LLM receives structured facts plus relevant schema/context.
l LLM converts facts into concise explanations.
l A validation layer checks that generated claims correspond to available computed facts.
l UI displays source/metric details where practical.
6.2 Example insight categories
l Trend: “Revenue increased between two periods.”
l Ranking: “Product X accounts for a large share of revenue.”
l Comparison: “Region A has lower sales volume than Region B.”
l Data quality: “17 rows have missing prices.”
l Outlier: “A small number of transactions are unusually large compared with the rest.”
l Opportunity: describe a measurable pattern, without pretending the data proves a business cause.
l Question: suggest what the user can investigate next.
6.3 Avoid false causality
The AI must distinguish correlation/pattern from cause. For example, it may say “sales declined in March
and Region X also declined” but should not claim that Region X caused the overall decline unless the data
actually supports such a conclusion and the methodology is appropriate.
7. Guided Analysis — The Signature Feature
The “Guide Me” experience turns a dashboard into an interactive analyst/tutor.
Example flow:
1. “Let's understand the big picture.” → show total revenue and orders.
2. “Now let's see where revenue comes from.” → Products.
3. “There's an unusual pattern.” → Region or month with notable change.
4. “Want to investigate?” → buttons such as Explore Region, Compare Products, Inspect Transactions.
This can be represented as an ordered investigation path generated from the workbook's highest-value
analytical opportunities, while allowing the user to skip any step.
8. Ask Your Excel — Natural Language Interface
The user should be able to ask questions without learning a query language.
AI Excel Copilot — Product & Technical Plan Page 5

l “Why did sales decrease in March?”
l “Which products are performing badly?”
l “Show me the best-performing commercial.”
l “What should I pay attention to?”
l “Find suspicious data.”
l “Explain this spreadsheet like I'm a beginner.”
l “Compare Oran and Alger.”
l “Show monthly revenue for 2026.”
l “What changed compared with last month?”
l “Which rows are causing this total?”
For each answer, the system should know whether it can answer directly, needs clarification, or cannot
reliably answer from the workbook.
9. Excel Formula Assistant
A later feature can turn the product into an Excel learning/debugging assistant.
l Explain the selected cell's formula in plain language.
l Identify likely reasons for #VALUE!, #REF!, #DIV/0!, #N/A and related errors.
l Explain dependencies/references.
l Suggest a corrected formula, with the user approving changes before applying them.
l Explain formulas to beginners step by step.
l Eventually allow formula generation from natural language.
10. Data Quality & Anomaly Detection
l Missing values.
l Duplicate rows.
l Inconsistent category spelling/casing.
l Mixed date formats.
l Invalid numeric values.
l Unexpected negative/zero values where suspicious.
l Extreme outliers.
l Broken formulas or formula inconsistencies.
l Potentially duplicated entities.
l Columns with mixed semantic types.
Important: an anomaly is a signal, not automatically an error. The UI should say “potential issue” and let
the user inspect the affected records.
11. Interface / UX Blueprint
AI Excel Copilot — Product & Technical Plan Page 6

11.1 Main dashboard
Suggested layout:
Sidebar: Overview, Trends, Products, Regions, People, Issues, Data, Ask AI.
Main area: workbook title, KPI cards, primary visualization, AI insights, guided next steps.
Right/secondary area where useful: explanation, filters, selected chart context.
11.2 Example screen structure
TOP: workbook name + sheet selector + filters + export/share.
ROW 1: KPI cards.
ROW 2: primary trend visualization.
ROW 3: AI insight cards + secondary comparisons.
ROW 4: data-quality warnings + suggested questions.
Persistent: Ask your Excel input.
11.3 UX rules
l Avoid a “cheap AI dashboard” look: prioritize hierarchy, whitespace, typography, restrained motion
and clarity.
l Show why each visualization exists.
l Keep advanced technical information one level deeper.
l Make every AI claim inspectable where feasible.
l Support desktop first; responsive web second.
l Do not force users to understand the internal AI pipeline.
12. Suggested Technical Architecture
A practical architecture can use a web frontend, API/backend, asynchronous analysis worker,
data-processing layer, LLM service, database, object storage, and visualization renderer.
High-level:
Browser → Web App → API → File Storage / Job Queue → Excel Parser → Data Profiler → Analytics Engine → Insight/LLM
Layer → Visualization Spec → Dashboard
12.1 Frontend
l Next.js / React is a strong option for the web application.
l TypeScript for maintainability.
l A charting library such as Recharts, ECharts or another robust React-compatible option.
l Drag-and-drop upload.
l Streaming/progressive analysis status.
l Interactive filters and drill-down.
12.2 Backend
l Node.js + TypeScript can handle API/auth/orchestration.
l Python is particularly useful for Excel parsing and data analysis.
l A separate analysis service can use Python libraries such as pandas and openpyxl.
AI Excel Copilot — Product & Technical Plan Page 7

l Use a queue for long-running analysis jobs.
l Keep LLM orchestration separate from deterministic analytics.
12.3 Storage
l Object storage for original workbooks and generated artifacts.
l PostgreSQL for users, workbooks, analysis jobs, schemas, metadata, saved analyses and usage.
l Optional Redis for queues/cache/rate limiting depending on architecture.
12.4 AI
l LLM for semantic interpretation, explanations, question understanding and guided analysis generation.
l Deterministic code for calculations and validation.
l Structured tool/function calls rather than asking the LLM to manually calculate large datasets.
l Prompt templates/versioning and evaluation datasets.
13. Internal Data Model
Object Purpose
User Account, plan, preferences, usage.
Workbook Uploaded file metadata and ownership.
Sheet Sheet-level metadata and profile.
ColumnProfile Type, role, statistics, quality information.
AnalysisJob Processing status, timing, errors and version.
Visualization Chart spec, title, source metrics and filters.
Insight Generated statement, supporting facts, confidence/status.
Question User question and answer context.
Finding Anomaly/data-quality item and affected rows/cells.
Report Saved/exported analysis artifact.
14. Analysis Pipeline — Detailed
Phase A: Upload → validate extension, size, malware/security policy, checksum.
Phase B: Parse → workbook/sheet/cell/table extraction.
Phase C: Normalize → dates, numeric representations, currencies/percentages, missing values, categories.
Phase D: Profile → distributions, cardinality, correlations where meaningful, formula metadata.
Phase E: Infer semantics → domain, entities, measures, dimensions, likely analytical goals.
Phase F: Generate candidates → KPIs, charts, insights, quality checks, questions.
AI Excel Copilot — Product & Technical Plan Page 8

Phase G: Score → usefulness, reliability, redundancy, readability.
Phase H: Validate → recompute metrics and verify AI claims.
Phase I: Render → dashboard and guided analysis.
Phase J: Interactive analysis → filters/questions trigger targeted recomputation.
Phase K: Export → PDF/report/image/PPT in later versions.
15. Security & Privacy
Excel files can contain sensitive business, financial, employee or customer information. Security is
therefore a core product requirement.
l Encrypt files in transit and at rest.
l Use strict per-user authorization for workbook access.
l Never expose another user's workbook through predictable URLs or IDs.
l Set retention/deletion controls.
l Limit file size, sheet size, analysis duration and resource consumption.
l Scan or sandbox potentially dangerous files before parsing.
l Treat formulas and external workbook references carefully.
l Do not execute macros/VBA.
l Avoid sending unnecessary raw rows to an external LLM.
l Log security-relevant actions without logging sensitive cell contents unnecessarily.
l Provide a clear privacy policy and deletion mechanism.
l Consider regional/legal requirements if selling to organizations.
16. MVP Scope
The first commercially meaningful version should stay focused.
Feature MVP
Excel upload Yes
Multiple sheets Yes, basic
Automatic schema detection Yes
Data profiling Yes
Automatic charts Yes
AI summary Yes
Data-quality warnings Yes
Ask your Excel Yes
Guided analysis Yes, basic
AI Excel Copilot — Product & Technical Plan Page 9

Feature MVP
Formula assistant Later
Automatic cleaning Later / limited preview
PDF export Yes if practical
PPT export Later
Sharing Later or basic
Geographic maps Later
Excel write-back Later
17. V2 Roadmap
l Better multi-sheet relationship inference.
l Saved dashboards.
l Advanced filtering and drill-down.
l Formula explanation.
l Suggested formula fixes.
l Automatic data-cleaning suggestions with preview/undo.
l More domain templates.
l PDF reports.
l Shareable analysis links.
l Team workspaces.
l More sophisticated anomaly detection.
l User feedback loop for improving generated insights.
18. V3 Roadmap
l PowerPoint report generation.
l Excel write-back with explicit user approval.
l Natural-language transformation of data.
l Advanced forecasting where statistically appropriate.
l Scenario analysis.
l Automated recurring workbook monitoring.
l Connect Google Sheets/CSV and eventually databases.
l Organization-level analytics workspaces.
l Role-based access control.
l API for developers.
AI Excel Copilot — Product & Technical Plan Page 10

l Enterprise governance and audit features.
19. Domain-Specific Examples
Workbook type Automatically detected analyses
Sales Revenue trends, products, salespeople, regions, average order, top/bottom
performers.
Finance / expenses Monthly spend, categories, budget vs actual, unusual transactions.
HR Headcount, department distribution, salary patterns, hiring trends, tenure.
Inventory Stock levels, inventory value, fast/slow-moving products, low-stock alerts.
Marketing Campaign performance, spend, conversions, channel comparisons, trends.
Education Grades, distributions, subject performance, class comparisons, outliers.
Project management Task status, deadlines, workload, completion trends, bottlenecks.
Generic dataset Profile-based charts and a neutral “Explore your data” workflow.
20. Monetization
A freemium SaaS model is a natural fit.
Plan Possible positioning
Free Limited files, rows, analyses or monthly AI usage.
Pro Higher limits, saved dashboards, exports, advanced AI analysis.
Team Shared workspaces, collaboration, permissions.
Business Higher limits, privacy controls, admin features, priority processing.
API Pay-per-analysis or usage-based developer API.
Pricing should be tested with real users rather than chosen purely from infrastructure cost. Track LLM cost,
file-processing cost, storage, bandwidth, support and payment fees before finalizing limits.
21. Metrics to Track
l Upload-to-completed-analysis rate.
l Median analysis completion time.
l Percentage of users who open a generated visualization.
l Percentage who click an insight or guided recommendation.
l Questions asked per workbook.
l Percentage of AI answers judged useful by users.
l Export rate.
AI Excel Copilot — Product & Technical Plan Page 11

l Return rate / repeat workbooks.
l Free-to-paid conversion.
l Average AI/data-processing cost per active user.
l Error rate by workbook type.
22. Quality & Evaluation Strategy
AI quality cannot be judged only by whether the interface looks impressive.
l Create a benchmark set of representative Excel workbooks.
l For each workbook, define expected schema interpretations and key metrics.
l Verify generated numerical claims against deterministic calculations.
l Test whether chart selection is sensible.
l Test whether explanations preserve the distinction between fact and interpretation.
l Test messy spreadsheets, multilingual headers, inconsistent formatting and missing values.
l Measure hallucination/unsupported-claim rate.
l Add human feedback on usefulness and clarity.
23. Implementation Plan
Phase Work
1. Foundation Repository, auth, upload UI, storage, database, basic job system.
2. Excel engine Parsing, sheet extraction, type detection, profiling and quality checks.
3. Analytics KPIs, aggregations, rankings, trends, anomaly candidates.
4. Visualization Chart-spec generator, dashboard renderer, filters and drill-down.
5. AI layer Schema interpretation, grounded insights, question answering.
6. Guided mode Suggested investigation path and contextual actions.
7. Export PDF/report generation; later PPT.
8. Hardening Security, quotas, monitoring, error handling, evaluation.
9. Beta Real users + feedback + benchmark testing.
10. Launch Pricing, onboarding, analytics, support and iteration.
24. Recommended MVP Technical Stack
Layer Suggested choice
Frontend Next.js + TypeScript
AI Excel Copilot — Product & Technical Plan Page 12

Layer Suggested choice
UI Tailwind CSS + accessible component system
Charts Recharts/ECharts or equivalent
API Node.js + TypeScript
Data processing Python + pandas + openpyxl
Database PostgreSQL
Queue/cache Redis or managed queue depending on deployment
Object storage S3-compatible storage
AI LLM API with structured outputs/tool calling
Auth Managed auth or secure application auth
Deployment Managed frontend + backend/worker infrastructure
Observability Error tracking + logs + usage metrics
This split lets you keep the main application in a stack comfortable for web development while using
Python where spreadsheet/data analysis is strongest.
25. Product Architecture Decisions to Avoid Early
l Do not let the LLM perform every calculation itself.
l Do not build a giant generic dashboard with dozens of charts.
l Do not assume every workbook has a clean rectangular table.
l Do not modify the original Excel silently.
l Do not build complex forecasting before basic profiling/insight quality works.
l Do not over-invest in dozens of integrations before Excel itself is excellent.
l Do not expose raw workbook data to AI providers unnecessarily.
l Do not treat every statistical pattern as a business recommendation.
26. The Long-Term Product Vision
If the core engine becomes reliable, the product can evolve from an “Excel analyzer” into a
general-purpose AI data understanding platform.
Long-term flow:
Excel → CSV → Google Sheets → databases → APIs → business data
The core abstraction becomes: connect data → understand schema → calculate facts → visualize → explain
→ guide → act.
At that point, Excel is the entry point rather than the limitation.
27. Example End-to-End Experience
AI Excel Copilot — Product & Technical Plan Page 13

Upload: ventes_2026.xlsx
AI: “I found 4,281 sales records across one main sheet. The data contains dates, products, regions, sales
representatives, quantity and price.”
Dashboard: total revenue, orders, average order, monthly trend, product ranking, regional comparison.
Insights: automatically generated statements supported by computed metrics.
Issues: 17 missing prices, several inconsistent product names, potential duplicate rows.
Guide: “Start with the monthly trend → investigate the March change → compare regions → inspect
affected transactions.”
Ask: “Why did March decline?”
Answer: generated from the relevant workbook calculations and displayed with supporting visualization.
Export: professional report for management.
28. One-Sentence Product Definition
An AI-powered Excel analyst that automatically understands a spreadsheet, creates the right
visualizations, explains what matters, finds potential problems, and guides the user toward useful
questions.
29. MVP Definition of Done
l A user can upload a real-world Excel workbook.
l The system can process at least common clean and moderately messy spreadsheets.
l The system correctly identifies sheets and major column types.
l The system computes trustworthy KPIs and aggregations.
l The system generates a small set of relevant visualizations.
l The system produces grounded insights.
l The user can ask questions about the workbook.
l The system can identify common data-quality issues.
l The user can follow suggested next analyses.
l The original workbook remains unchanged.
l Errors and unsupported cases are clearly communicated.
l Sensitive files are protected and deletable.
l The system has measurable evaluation tests before public launch.
AI Excel Copilot — Product & Technical Plan Page 14

BUILD THE ANALYST, NOT JUST
THE CHART GENERATOR.
The strongest version of the product is not “upload Excel and get graphs.” It is a system
that reduces the distance between raw spreadsheet and understanding.
Core loop: Upload → Understand → Visualize → Explain → Guide → Ask → Act
Start narrow with Excel. Make the understanding engine excellent. Then expand the same engine to other
data sources.
AI Excel Copilot — Product & Technical Plan Page 15
