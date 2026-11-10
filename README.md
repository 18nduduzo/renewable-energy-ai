---
title: Solar & Electrical Design AI
emoji: ⚡
colorFrom: yellow
colorTo: green
sdk: streamlit
app_file: app.py
pinned: false
---

# ⚡ Solar & Electrical Design AI

AI chat assistant plus engineering calculators for solar PV, batteries, inverters,
cables, power factor correction and ROI. Built for Eswatini and Southern Africa.

(The block at the top of this file is required by Hugging Face Spaces. Keep it.)

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit interface and AI chat |
| `calculators.py` | Engineering formulas (no UI, easy to test) |
| `requirements.txt` | Python dependencies |

## Run locally

```bash
pip install -r requirements.txt
export GROQ_API_KEY=gsk_your_key      # Windows PowerShell: $env:GROQ_API_KEY="gsk_your_key"
streamlit run app.py
```

## Deploy on Hugging Face Spaces (free)

1. Create a Space: SDK **Streamlit**, visibility Public.
2. Upload `app.py`, `calculators.py`, `requirements.txt`, `README.md`.
3. Settings → **Variables and secrets** → add secret `GROQ_API_KEY`.
4. Optional secrets:
   - `MODEL` (default `openai/gpt-oss-120b`). Change this when Groq retires a model.
   - `FALLBACK_MODEL` (default `openai/gpt-oss-20b`).
   - `APP_PASSWORD`. Set this to stop strangers using up your free API quota.

## Never commit your API key

Do not put the key in code or in GitHub. Use Secrets only. If a key leaks, delete it in the Groq console and create a new one.

## Disclaimer

Outputs are first-pass design estimates. Verify with manufacturer datasheets and local
regulations, and have a qualified person sign off any installation.
