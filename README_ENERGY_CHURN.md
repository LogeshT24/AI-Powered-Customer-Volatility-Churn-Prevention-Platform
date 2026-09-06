# Energy Retention Command Centre

An explainable, service-first churn early-warning prototype for the Centrica hackathon. It adds a **Customer Volatility Score** to a normal churn model so unresolved service failures, sentiment deterioration and external energy-market stress are recognised before a customer chooses to switch.

## What is in this prototype

- `registries/energy_churn.hocon`: a Neuro SAN network with a retention coordinator and three specialist agents.
- `coded_tools/energy_churn/energy_tools.py`: deterministic scoring, intervention policy and portfolio aggregation. These tools keep calculations out of the LLM.
- `data/energy_churn_demo.csv`: eight entirely synthetic, pseudonymised demo customers. It must be replaced by governed CRM, billing, complaints, smart-meter and contact-centre views before any production use.

## Architecture

```text
retention_command_centre
  ├── customer_risk_agent ── Customer360Tool, VolatilityScoreTool
  ├── sentiment_agent ────── Customer360Tool
  └── intervention_agent ─── InterventionTool
```

The score is transparent and bounded to 0–100:

`25% complaint handling + 20% resolution timeliness + 20% sentiment + 20% market impact + 15% customer behaviour`

Bands: Stable (<35), Watch (35–54), High (55–74), Critical (75+). The current churn probability is deliberately a deterministic **demo baseline**, not a trained model or an automated decision.

## Run the project

### One-time setup (PowerShell)

Run these commands from the repository root:

```powershell
Copy-Item .env.example .env
# Edit .env and replace YOUR_GOOGLE_GEMINI_API_KEY with a valid Gemini key before using the Neuro SAN agent.

py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

Push-Location apps\energy_churn_dashboard
npm install
Pop-Location
```

The network is already registered as `"energy_churn.hocon": true` in
`registries/manifest.hocon`. Do not replace the manifest: add any future networks alongside
the existing entries.

### Terminal 1 — Neuro SAN Studio and the agent

```powershell
cd C:\workspace\neuro-san-studio
.\.venv\Scripts\ns.exe run
```

Wait until the server finishes loading (the full example manifest can take about two minutes),
then open [http://localhost:4173](http://localhost:4173). In the left **Available Agents**
panel, click **CONNECT** for `localhost:8080`, search for `energy_churn`, and drag it to the
canvas. The internal agents are displayed inside that network; the left panel lists the
top-level network only.

To run only the API that serves the Neuro SAN agent, without starting the Studio UI:

```powershell
.\.venv\Scripts\ns.exe run --server-only
```

### Terminal 2 — Energy Churn dashboard API

```powershell
cd C:\workspace\neuro-san-studio
.\.venv\Scripts\python.exe -m apps.energy_churn_api.app
```

The Flask API runs at [http://127.0.0.1:5000](http://127.0.0.1:5000). It uses only the bundled
synthetic dataset by default, so the dashboard works without an LLM key. The Neuro SAN agent
uses `GOOGLE_API_KEY` with Gemini.

### Terminal 3 — Energy Churn React dashboard

```powershell
cd C:\workspace\neuro-san-studio\apps\energy_churn_dashboard
npm run dev
```

Open the Vite URL shown in the terminal, normally [http://127.0.0.1:5173](http://127.0.0.1:5173).

### Quick health checks

```powershell
# Lists networks exposed by the running Neuro SAN server; look for energy_churn.
Invoke-RestMethod http://localhost:8080/api/v1/list

# Returns the Energy Churn dashboard summary.
Invoke-RestMethod http://127.0.0.1:5000/api/dashboard
```

The implemented demo has two complementary surfaces: Neuro SAN nsflow shows the three-agent
orchestration and chat flow, while a local React dashboard presents the command-centre portfolio.
Flask owns the local SQLite API; no external CRM, MCP server, cloud database, or separate
orchestration framework is required.

The dashboard defaults to deterministic policy citations for a fast offline demo. To enable the
local Chroma vector store, set `OPENAI_API_KEY`, `OPENAI_EMBEDDING_MODEL`, and
`POLICY_VECTOR_ENABLED=true`. The market card uses Energy-Charts when online and clearly labels a
packaged fallback snapshot when it is not.

## Demo prompts and expected results

| Prompt | Expected evidence-led result |
| --- | --- |
| `Assess C-1002 and recommend an intervention.` | Critical/High risk, driven by 40% SLA, repeat escalated complaints, negative sentiment, direct-debit cancellation and high market exposure; route to a senior complaint owner and payment-support review. |
| `Show the retention command-centre dashboard.` | Portfolio size, average volatility, Critical/High count and top five pseudonymised priority cases. |
| `Why is C-1001 a loyal customer?` | Stable score with strong SLA, no repeat complaints and positive feedback. |

## Production path and guardrails

1. Land source data behind approved connectors; retain customer identifiers only in Sly Data or controlled tools, not prompts/logs.
2. Train LightGBM/CatBoost against an explicit churn label and time-based holdout; track AUC, PR-AUC, calibration, intervention uplift and fairness slices.
3. Ground the Market Intelligence Agent only in approved Ofgem/market feeds, carrying source URL and timestamp in every result.
4. Require human approval for pricing, tariff movement, payment plans and vulnerability-related contact; log explanation, action and outcome.
5. Monitor score drift, model drift, complaint resolution outcomes and false-positive intervention rate.
