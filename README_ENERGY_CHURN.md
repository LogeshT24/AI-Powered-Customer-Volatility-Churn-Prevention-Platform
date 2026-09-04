# Energy Retention Command Centre

An explainable, service-first churn early-warning prototype for the Centrica hackathon. It adds a **Customer Volatility Score** to a normal churn model so unresolved service failures, sentiment deterioration and external energy-market stress are recognised before a customer chooses to switch.

## What is in this prototype

- `registries/energy_churn.hocon`: a six-specialist Neuro SAN agent network plus an executive Dashboard Agent.
- `coded_tools/energy_churn/energy_tools.py`: deterministic scoring, intervention policy and portfolio aggregation. These tools keep calculations out of the LLM.
- `data/energy_churn_demo.csv`: eight entirely synthetic, pseudonymised demo customers. It must be replaced by governed CRM, billing, complaints, smart-meter and contact-centre views before any production use.

## Architecture

```text
Retention Command Centre
  ├── Customer Intelligence ── Customer360Tool
  ├── Complaint Resolution ── VolatilityScoreTool
  ├── Sentiment ──────────── Customer360Tool
  ├── Market Intelligence ── Customer360Tool
  ├── Churn Prediction ───── VolatilityScoreTool
  ├── Intervention ───────── InterventionTool
  └── Dashboard ──────────── PortfolioDashboardTool
```

The score is transparent and bounded to 0–100:

`25% complaint handling + 20% resolution timeliness + 20% sentiment + 20% market impact + 15% customer behaviour`

Bands: Stable (<35), Watch (35–54), High (55–74), Critical (75+). The current churn probability is deliberately a deterministic **demo baseline**, not a trained model or an automated decision.

## Launch in Neuro SAN Studio

1. Ensure this network is included by your `registries/manifest.hocon` (use the existing manifest convention; do not replace other entries).
2. Set `AGENT_TOOL_PATH` to this project’s `coded_tools` directory and configure your LLM key in `.env`.
3. Run `ns run` from the project folder.
4. Open the nsflow UI at `http://localhost:4173`, select **Retention Command Centre**, then test the prompts below.

The implemented demo has two complementary surfaces: Neuro SAN nsflow shows the three-agent
orchestration and chat flow, while a local React dashboard presents the command-centre portfolio.
Flask owns the local SQLite API; no external CRM, MCP server, cloud database, or separate
orchestration framework is required.

## Local dashboard launch

1. Install Python dependencies from `requirements.txt`.
2. Start the Flask API: `python -m apps.energy_churn_api.app`.
3. In `apps/energy_churn_dashboard`, run `npm install` once and `npm run dev`.
4. Open the Vite URL, normally `http://127.0.0.1:5173`.

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
