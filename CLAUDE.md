# CLAUDE.md - Month-End Close Manager
# Helvetia Advisory AG - AI-Assisted FP&A Close Tool
# Project Brief for Claude Code

---

## PROJECT OVERVIEW

Build a production-quality AI-assisted month-end close management tool for FP&A teams. The app replaces the typical Excel or shared document used to track close progress with a structured, intelligent tracker showing real-time close status across multiple business units, flagging exceptions, and using AI to assist with the most time-consuming analytical and communication tasks in the close cycle.

The demo represents Helvetia Advisory AG, a Swiss technology company headquartered in Zurich, at a WD+1 snapshot - mid-close, with three DACH business units in different states of progress, active escalations, and AI features firing across the workflow.

This is a portfolio and demonstration application. It must look professional, perform reliably, and be explainable to a Swiss FP&A hiring manager or CFO in a live demo.

---

## PROJECT STRUCTURE

```
~/close-tracker/
├── CLAUDE.md               (this file)
├── app.py                  (main Streamlit application)
├── .env                    (API key placeholder - never commit)
├── .gitignore              (excludes .env, venv/, __pycache__/)
├── requirements.txt        (to be created)
├── venv/                   (Python virtual environment)
└── data/
    ├── FPnAMonth-EndCloseWorkflow.xlsx      (Task Master - primary data source)
    └── Helvetia_AG_AI_Synthetic_Datasets.xlsx  (AI feature datasets)
```

---

## TECH STACK

- **Python 3.x** - core application language
- **Streamlit** - web application framework
- **Pandas** - data reading and processing (read directly from Excel, Option A)
- **OpenPyXL** - Excel file handling (engine for pandas)
- **Anthropic Claude API** - powers all six AI features (hybrid manual workflow for prototype)
- **python-dotenv** - environment variable management

Install dependencies:
```
pip install streamlit pandas openpyxl anthropic python-dotenv
```

Create requirements.txt with these packages after confirming they install correctly.

---

## PRIMARY DATA SOURCE - TASK MASTER

File: `data/FPnAMonth-EndCloseWorkflow.xlsx`
Sheet to read: `Task Master`

Read with:
```python
import pandas as pd
df = pd.read_excel('data/FPnAMonth-EndCloseWorkflow.xlsx', sheet_name='Task Master')
```

### Key columns used by the app

| Column | Purpose |
|--------|---------|
| Task ID | Unique identifier, used for all references |
| Working Day | WD-5 through WD+3, used for timeline display |
| Phase | Pre-Close, Close, Close-to-Post-Close, Post-Close |
| Organization Level | BU, Region, Area, Global |
| Lowest Org Level Name | BU001, BU002, BU003, DACH, EMEA, Global |
| Country | Switzerland, Germany, Austria, NA |
| Task Owner | Role name of primary owner |
| Task Description | Plain English task description |
| Status | Not Started, In Progress, Complete, Blocked |
| Completion % | Integer 0, 50, or 100 |
| Priority | High, Medium, Low |
| SLA Hours | Hours allocated to complete the task |
| Escalated | Yes or No |
| AI Enabled | Yes or No |
| AI Action | Description of AI task when AI Enabled = Yes |
| AI Confidence Threshold | 0-100 integer |
| Comments | Free text close notes |
| Escalation Role | Who gets notified on breach |
| Escalation After Hours | Hours after SLA breach before escalation fires |
| Human Approval Required | Yes or No |
| Approval Role | Who approves |
| Variance Threshold Rule ID | VR001-VR004 |
| Escalation Rule ID | ER001-ER006 |
| Functional Currency | CHF or EUR |
| Reporting Currency | CHF throughout |

### Supporting sheets (reference only, not read dynamically)
- Index: data dictionary
- Variance Rules: VR001-VR004 threshold definitions
- Exception Rules: ER001-ER006 escalation conditions
- Approval Workflow: four-level approval framework
- AI Features: Wave 1 feature list

### Entity structure
- BU001 - Switzerland - CHF - Mid-close, 2 blocked tasks, AI active
- BU002 - Germany - EUR - Behind schedule, multiple blocked tasks, 3 escalated
- BU003 - Austria - EUR - Clean close, mostly complete
- DACH Region - Consolidation in progress, at risk due to Germany
- EMEA Area - Not started, waiting on DACH
- Global - Not started

---

## AI DATASETS - SECONDARY DATA SOURCE

File: `data/Helvetia_AG_AI_Synthetic_Datasets.xlsx`

Each sheet feeds one AI feature. Read the relevant sheet when the corresponding AI feature button is triggered.

| Sheet Name | AI Feature | Entity/Scope |
|-----------|-----------|-------------|
| Suggested Accruals | Feature 2 | BU001 Switzerland |
| Variance Root Cause | Feature 3 | DACH Region consolidated |
| Missing Account Checks | Feature 4 | BU001 Switzerland |
| Narrative Consistency Check | Feature 5 | BU001 Switzerland |
| Headcount Exception Detection | Feature 6 | DACH Region (all 3 BUs) |

Read example:
```python
df_accruals = pd.read_excel(
    'data/Helvetia_AG_AI_Synthetic_Datasets.xlsx',
    sheet_name='Suggested Accruals'
)
```

---

## APP ARCHITECTURE - FIVE PHASES

Build in this exact order. Each phase must be tested before starting the next.

### Phase A - Core Tracker
Task list renders with all columns, grouped by Phase and filterable by Entity. Status displays with colour coding. Escalated tasks show alert indicator. Data is read-only display - no editing in Phase A.

### Phase B - Dashboard
Summary metrics panel above the task list. Progress bar, percentage complete, task counts by status, escalated count, per-entity completion breakdown showing three BU stories visually.

### Phase C - AI Email Draft (Feature 1)
Single button on the dashboard. Reads current task state from the full dataframe, formats a structured context string, displays a text area where the AI-generated CFO status email will appear. For the prototype, the text area is pre-populated with a realistic email. The button and text area UI must be built production-ready so the live API call can be wired in later.

### Phase D - Five Additional AI Features (Features 2-6)
Each AI feature has a labelled trigger button in a dedicated AI Analysis section. When clicked, reads the relevant sheet from the AI datasets file, formats the data as a structured context string, and displays the AI output in a clean output panel. For the prototype, outputs are pre-populated with realistic analysis text derived from the actual dataset content. Build one feature at a time, test each before building the next.

### Phase E - Password Authentication
Simple Streamlit sidebar password gate. Anyone can view the app. Editing task status and triggering AI features requires password entry. Password stored in Streamlit secrets, never hardcoded.

---

## DETAILED UI SPECIFICATION

### Page layout
- Wide layout: `st.set_page_config(layout="wide")`
- Page title: "Helvetia Advisory AG - Month-End Close Manager"
- Subtitle: "FP&A Close Tracker | Fiscal Period 2026 P05 | Snapshot: WD+1"

### Sidebar
- App title and logo area
- Entity filter: multiselect of all unique Lowest Org Level Name values
- Phase filter: multiselect of all unique Phase values
- Status filter: multiselect (Not Started, In Progress, Complete, Blocked)
- Password input field (Phase E)
- "About this app" expander with brief description

### Dashboard section (Phase B)
Displayed as metric cards in a row:
- Total tasks
- Complete (count and %)
- In Progress (count)
- Blocked (count) - displayed in red
- Escalated (count) - displayed in amber
- Overall progress bar

Per-entity completion table below metrics:
- Rows: BU001 Switzerland, BU002 Germany, BU003 Austria, DACH Region, EMEA Area, Global
- Columns: Total Tasks, Complete, In Progress, Blocked, Not Started, Completion %
- Colour code completion % column: green >70%, amber 30-70%, red <30%

### Task list section (Phase A)
Grouped by Phase, then sorted by Working Day within each phase.
Display columns: Task ID, Working Day, Task Description, Organization Level, Country, Task Owner, Status, Completion %, Priority, Escalated, Comments

Status colour coding:
- Complete: green background
- In Progress: amber background
- Blocked: red background
- Not Started: light grey background

Escalated = Yes: show red flag icon or "ESCALATED" badge next to status

### AI Analysis section (Phase D)
Placed below the task list.
Tab-based layout with one tab per AI feature:
- Tab 1: CFO Status Email Draft
- Tab 2: Suggested Accruals
- Tab 3: Variance Root Cause
- Tab 4: Missing Account Checks
- Tab 5: Narrative Consistency Check
- Tab 6: Headcount Exception Detection

Each tab contains:
- Brief description of what the AI feature does (1-2 sentences)
- Trigger button labelled clearly e.g. "Generate Suggested Accruals Analysis"
- Output panel (st.text_area or st.markdown) where result appears
- Data source label: which file and sheet the feature reads from

---

## AI FEATURE SPECIFICATIONS

### Feature 1 - CFO Status Email Draft
Trigger: "Generate CFO Status Email" button on dashboard
Data source: Task Master dataframe (already loaded)
Context to pass to AI: summary of total tasks, complete/blocked/in-progress counts, names of blocked tasks with owner and comments, escalated tasks, DACH consolidation status
Output format: Formal email, subject line, greeting to CFO, structured body covering overall status, issues requiring attention, expected resolution timeline, closing

Prototype pre-populated output should reflect:
- Austria clean, Switzerland mid-close with 2 blocked items (AR CHF 87K, AP CHF 43K)
- Germany delayed, DACH consolidation at risk
- Variance analysis flagging CHF 156K contractor overage

### Feature 2 - Suggested Accruals
Trigger: Button in AI Analysis tab
Data source: Suggested Accruals sheet from Helvetia_AG_AI_Synthetic_Datasets.xlsx
Context: Full sheet content including account codes, 3M averages, current submissions, variances, and AI Flag column
Output format: Numbered list of suggested accruals with account code, account name, suggested amount, and reason. Summary of total estimated missing accruals.

Key findings to reflect in output:
- Software Licence Renewals account 6300: CHF 28K missing, recurring monthly charge
- Legal & Professional Fees account 6600: CHF 13.5K missing, legal retainer
- IC Recharge to BU002 account 7000: CHF 45K missing, monthly recharge not submitted
- T&E account 6500: submission 86% below average, confirm with cost centre owner
- Total estimated missing: CHF 86.5K

### Feature 3 - Variance Root Cause Suggestions
Trigger: Button in AI Analysis tab
Data source: Variance Root Cause sheet from Helvetia_AG_AI_Synthetic_Datasets.xlsx
Context: Full P&L table including budget, actuals, variance amounts and percentages, threshold breach flags, driver categories, and AI root cause notes
Output format: Structured variance narrative by P&L section (Revenue, OPEX, Below the line, EBIT summary), with specific amounts and driver explanations

Key findings to reflect in output:
- Revenue CHF 80K favourable: software licences +3.2% from new enterprise client
- Personnel contractor CHF 156K adverse: 4 unplanned contractors - VR002 threshold breach
- Personnel salaries CHF 72K adverse: 3 unplanned engineering hires
- T&E CHF 25K favourable: Q2 events postponed
- FX CHF 22K adverse: EUR/CHF 0.9412 vs budget 0.9580 (168 basis points weaker)
- EBIT CHF 178K adverse: contractor overage primary driver

### Feature 4 - Missing Account Checks
Trigger: Button in AI Analysis tab
Data source: Missing Account Checks sheet from Helvetia_AG_AI_Synthetic_Datasets.xlsx
Context: Full account list with P04 balances, P05 balances, expected to post flag, zero balance flag, and AI notes
Output format: List of flagged accounts with account code, account name, expected amount, investigation status, and recommended action

Key findings to reflect in output:
- Account 2400 IC Payable BU002: CHF 45K zero balance, monthly recharge not posted
- Account 6300 Software Licence Renewals: CHF 28K zero balance, recurring accrual missing
- Account 6600 Legal & Professional Fees: CHF 13.5K estimated, retainer not accrued
- All other 21 accounts have expected balances or legitimate zero balances

### Feature 5 - Narrative Consistency Check
Trigger: Button in AI Analysis tab
Data source: Narrative Consistency Check sheet from Helvetia_AG_AI_Synthetic_Datasets.xlsx
Context: Section A draft commentary paragraphs and Section B AI check results including reported figures, stated figures, consistency status, and recommendations
Output format: Commentary review results paragraph by paragraph showing what was stated vs what the numbers show, with specific recommended rewrites for inconsistent paragraphs

Key findings to reflect in output:
- Para 1 Revenue: states 2% above forecast, actual is 3.2% - INCONSISTENT
- Para 2 Contractor: states "some additional project support", actual is CHF 156K material breach - INCONSISTENT MATERIAL
- Para 3 Salaries: states "normal movements within approved plan", actual is 3 unplanned hires - INCONSISTENT
- Para 4 T&E: consistent, no change required
- Para 5 FX: does not disclose CHF 22K adverse vs budget, 168 basis points rate differential - INCONSISTENT
- Para 6 EBIT: states "marginally below budget", actual is CHF 178K adverse - INCONSISTENT

### Feature 6 - Headcount Exception Detection
Trigger: Button in AI Analysis tab
Data source: Headcount Exception Detection sheet from Helvetia_AG_AI_Synthetic_Datasets.xlsx
Context: Full department-level headcount table for all three BUs with approved plan, actual, hires, exits, variances, cost impacts, and AI exception flags
Output format: Exception summary by entity, department-level exceptions with cost impact, DACH consolidated summary, and recommended actions

Key findings to reflect in output:
- BU001 Switzerland: 3 unplanned engineering hires, CHF 55.5K/month, net +2 vs plan
- BU002 Germany: 5 departments with exceptions, 12 total position changes from restructuring, EUR 67K/month adverse
- BU002 Sales: 3 vacancies from restructuring, DACH South territory coverage risk
- BU003 Austria: no exceptions, fully within plan
- DACH total: +7 vs plan, 7 departments with exceptions
- Recommend escalation to DACH Finance Manager

---

## PROTOTYPE AI OUTPUT APPROACH

For this prototype, AI feature outputs are pre-populated with realistic analysis derived directly from the actual dataset content. This is the agreed hybrid approach - the UI is built production-ready with proper button triggers and output panels, but the API call is not wired live.

When building the prototype outputs, use the key findings listed above for each feature. Write the outputs in a professional FP&A tone appropriate for a Controller or CFO audience. Do not make the outputs sound generic - they must reference specific amounts, account codes, entity names, and drivers from the actual data.

The code structure should include a commented placeholder for the live API call so it is easy to activate in a future session:

```python
# PROTOTYPE: pre-populated output below
# TO ACTIVATE LIVE API: uncomment the anthropic call block and remove the static output
```

---

## AUTHENTICATION SPECIFICATION (Phase E)

Implementation: Streamlit sidebar password input + session state

```python
# Pattern to implement:
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False

password = st.sidebar.text_input("Edit access password", type="password")
if password == st.secrets["EDIT_PASSWORD"]:
    st.session_state.authenticated = True
```

View access: always available, no password required
Edit access (status updates, AI feature triggers): requires authentication

For local development, store password in .streamlit/secrets.toml:
```toml
EDIT_PASSWORD = "helvetia2026"
```

This file must be added to .gitignore. Never commit secrets.toml.

---

## CODING STANDARDS

- All column references use exact names from the Task Master - no renaming
- Handle missing or NaN values gracefully - do not crash on blank cells
- Use `st.cache_data` decorator on data loading functions to prevent re-reading files on every interaction
- Separate data loading, business logic, and UI rendering into distinct functions
- Use consistent colour variables defined once at the top of app.py
- No hardcoded file paths - use relative paths from the project root
- Comments in English throughout
- Do not use em dashes anywhere in string literals or UI text - use hyphens only

### Colour palette
```python
COLOR_COMPLETE = "#E2EFDA"      # green
COLOR_IN_PROGRESS = "#FFF2CC"   # amber
COLOR_BLOCKED = "#FFCCCC"       # red
COLOR_NOT_STARTED = "#F2F2F2"   # light grey
COLOR_ESCALATED = "#FF0000"     # red text
COLOR_PRIMARY = "#1F4E79"       # dark blue - Helvetia brand
COLOR_SECONDARY = "#2E75B6"     # medium blue
COLOR_ACCENT = "#D6E4F0"        # light blue
```

---

## WHAT DONE LOOKS LIKE BY PHASE

**Phase A complete:** App loads, task list renders grouped by phase, all columns visible, status colour coding applied, entity and phase filters work, escalated badge visible on blocked tasks.

**Phase B complete:** Dashboard metrics render correctly from live data. Progress bar reflects actual completion percentage. Per-entity table shows three distinct BU stories. All counts match the underlying data.

**Phase C complete:** CFO email button visible on dashboard. On click, realistic pre-populated email appears in text area. Email references Switzerland blockages, Germany delays, DACH consolidation risk, and contractor variance specifically.

**Phase D complete:** AI Analysis section with six tabs renders. Each tab has a trigger button and output panel. All six features produce specific, realistic output derived from actual dataset content. Output does not look generic.

**Phase E complete:** Password input in sidebar. Edit mode locked behind password. View-only mode works without password. Correct password unlocks status update capability and AI feature triggers.

---

## DEMO SCENARIO CONTEXT

The app snapshot represents Helvetia Advisory AG at WD+1 of the May 2026 close (2026 P05).

Austria (BU003): Clean close. All BU-level tasks complete. Submitted ahead of schedule.

Switzerland (BU001): Mid-close. Pre-close complete. Two WD-1 tasks blocked - AR reconciliation (CHF 87K unapplied receipts) and AP posting (2 unbooked invoices CHF 43K). Post-close analysis in progress with AI features active.

Germany (BU002): Behind schedule. Restructuring programme created 12 unplanned headcount changes. AR and AP both blocked. FX revaluation cannot run. Subledger not closed. P&L not generated. Two tasks escalated.

DACH Region: Consolidation in progress at 30%. Austria submitted, Switzerland partial, Germany delayed. Escalation risk if Germany does not close by WD+1 12:00.

EMEA and Global: Not started, waiting on DACH pack.

Inter-company context: EUR 62K inter-co mismatch between BU001 Switzerland and BU002 Germany treasury teams outstanding. Under investigation.

---

## SESSION STARTUP INSTRUCTIONS FOR CLAUDE CODE

At the start of every Claude Code session:
1. Read this CLAUDE.md file
2. Read the current state of app.py
3. Confirm the data folder contains both xlsx files
4. Confirm the virtual environment is active
5. State which Phase you are about to build before writing any code
6. Use Plan Mode - propose the approach and wait for approval before modifying files

When I ask you to build something, default to the smallest working increment first, then iterate. Do not build all phases in one session.
