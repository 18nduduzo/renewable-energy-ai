# ⚡ Solar & Electrical Design AI

AI chat assistant plus engineering calculators for solar PV, batteries, inverters,
cables, power factor correction and ROI. Built for Eswatini and Southern Africa.

## Features

- ChatGPT-style chats: new chat, chat list, regenerate, continue (when a reply is cut off), export to Markdown
- Several AI providers: Groq, Google Gemini, xAI Grok, OpenAI. A provider shows up once you add its key.
  If the chosen one fails or hits a limit, the others are tried automatically.
- Calculators: solar + inverter, battery, cable (voltage drop), power factor, ROI
- Proper maths rendering for equations

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit interface |
| `providers.py` | AI providers, failover, history trimming |
| `chatstore.py` | Saving conversations (memory or SQLite) |
| `calculators.py` | Engineering formulas |
| `mathfmt.py` | Fixes equation formatting from the AI |
| `test_core.py` | Tests (`python test_core.py`) |
| `secrets.example.toml` | Template for your keys |

## Run locally

```bash
pip install -r requirements.txt
cp secrets.example.toml .streamlit/secrets.toml     # then edit it and add a key
streamlit run app.py
```

## Deploy (free): Streamlit Community Cloud

Hugging Face no longer offers Streamlit as a free SDK. Use https://share.streamlit.io:
connect GitHub, pick this repo, main file `app.py`, and paste your secrets under Advanced settings.

## Which providers are free?

(Based on third-party summaries in Nov 2026. Check each vendor's current terms.)

- **Groq**: free tier for testing. Use a paid plan for real customers.
- **Gemini**: free tier on Flash models with small daily limits. Google may use free-tier prompts to improve its products, so do not send confidential client data.
- **xAI Grok** and **OpenAI**: pay-as-you-go. No free API credits for new accounts.

Model names change often. Override them with secrets (see `secrets.example.toml`).

## Saved chats: read before turning on

By default chats live only in the visitor's browser session and disappear on refresh.
`PERSIST_CHATS=true` saves them to a local file (`chats.db`). On free hosts that file is temporary
and **shared by every visitor**, so only enable it on your own computer, or after adding user login
(then pass each user's id as `OWNER` in `app.py` so people only see their own chats).

## Never commit your API keys

Keys belong in `.streamlit/secrets.toml` or your host's Secrets page, never in code or GitHub.
If a key leaks, delete it in the provider's console and create a new one.

## Disclaimer

Outputs are first-pass design estimates. Verify with manufacturer datasheets and local
regulations, and have a qualified person sign off any installation.
