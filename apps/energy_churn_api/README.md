# Energy Retention Command Centre API

Run the local demo API from the repository root:

```powershell
.\.venv\Scripts\python.exe -m apps.energy_churn_api.app
```

The API seeds only pseudonymised synthetic data into `data/energy_churn.db`. It uses a live
Energy-Charts request when possible and transparently serves `data/market_fallback.json` when
offline. Configure `OPENAI_API_KEY` and `OPENAI_EMBEDDING_MODEL` to enable persistent Chroma policy
retrieval by also setting `POLICY_VECTOR_ENABLED=true`; source-file retrieval remains the fast,
offline-safe default for the dashboard.
