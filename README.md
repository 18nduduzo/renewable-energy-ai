# ⚡ Solar & Electrical Design AI

AI chat assistant plus engineering calculators for solar PV, batteries, inverters,
cables, power factor correction and ROI. Built for Eswatini and Southern Africa.

## Features

- ChatGPT-style chats: new chat, chat list, regenerate, continue (when a reply is cut off), export to Markdown
- Several AI providers: Groq, Google Gemini, xAI Grok, OpenAI. A provider shows up once you add its key.
  If the chosen one fails or hits a limit, the others are tried automatically.
- Calculators: solar + inverter, battery, cable (voltage drop), power factor, ROI
- Proper maths rendering for equations
- **Drawings (paid PDFs):** single line diagram, array layout, rails and mounting detail for pitched roofs, flat roofs and ground mounts, plus bill of materials and cable/protection schedules

## Files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit interface |
| `providers.py` | AI providers, failover, history trimming |
| `chatstore.py` | Saving conversations (memory or SQLite) |
| `calculators.py` | Engineering formulas |
| `mathfmt.py` | Fixes equation formatting from the AI |
| `design.py` | String sizing, protection, cables, bill of materials |
| `layout.py` | Module layout, rails, clamps, posts, row spacing |
| `scene.py` | Drawing model that renders to SVG (preview) and PDF |
| `drawings.py` | The five A3 drawing sheets |
| `drawings_ui.py` | The Drawings screen |
| `paywall.py`, `make_codes.py` | Signed unlock codes for paid downloads |
| `test_drawings.py` | Tests for the drawing features |
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

## Selling the drawing PDFs

Everyone sees the design numbers and watermarked previews. The clean PDFs need an unlock code.

1. Choose a long random `UNLOCK_SECRET` and add it to the app's Secrets (and keep a copy somewhere safe).
2. A customer pays you (bank transfer / mobile money). Then you make a code on your own computer:

```bash
export UNLOCK_SECRET="the-same-secret"
python make_codes.py PACK ACME 30      # complete pack, valid 30 days
python make_codes.py SLD  JOHNS 7      # single line diagram only, valid 7 days
```

3. Send them the code. They paste it into the Drawings view and the PDF buttons appear.

Codes are stateless: they can be shared until they expire, and cannot count downloads. Use short expiries,
and add a customer id to `REVOKED_CODES` to cut one off. For automatic card payments and per-download credits you
will later need a database and a payment provider that pays out to Eswatini (Stripe does not).

**The drawings are preliminary.** They are generated from your inputs, are not stamped, and must be checked and signed
off by a registered engineer or competent electrician. Wind, snow, foundations and ballast are not calculated.
Have a lawyer review your terms of sale before you charge.

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
