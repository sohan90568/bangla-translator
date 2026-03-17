# 🔤 Bangla AI Translator — Production v2.0

Professional Bangla ↔ English AI translation with full user auth, payments, and analytics.

**Stack:** Python · Streamlit · Groq AI · PortPos · SQLite · bcrypt

---

## Folder structure

```
bangla_translator/                  ← your project root
│
├── app.py                          ← main app (run this)
├── config.py                       ← all settings in one place
├── auth.py                         ← login, register, password reset
├── database.py                     ← SQLite — all 12 tables
├── translator.py                   ← Groq AI translation engine
├── payments.py                     ← PortPos payment integration
├── email_service.py                ← Gmail SMTP notifications
├── requirements.txt                ← Python dependencies
│
├── .streamlit/
│   ├── config.toml                 ← Streamlit theme + server settings
│   └── secrets.toml                ← secrets for Streamlit Cloud (never commit)
│
├── .env                            ← secrets for local testing (never commit)
├── .env.example                    ← template — safe to commit
├── .gitignore                      ← protects .env, .db, secrets.toml
├── Procfile                        ← for Railway.app deployment
│
└── data/                           ← auto-created on first run
    └── translator.db               ← SQLite database (never commit)
```

---

## Local setup (5 minutes)

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Create .env file
Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```
Then open `.env` in VS Code and fill in:
```
GROQ_API_KEY=gsk_your_key_from_console.groq.com
ADMIN_PASSWORD=YourPassword@123
PORTPOS_SANDBOX=true
PORTPOS_APP_KEY=your_sandbox_key_from_sandbox.portpos.com
PORTPOS_SECRET_KEY=your_sandbox_secret_from_sandbox.portpos.com
APP_URL=http://localhost:8501
```

### 3. Run
```bash
streamlit run app.py
```

App opens at: http://localhost:8501

---

## Streamlit Cloud deployment

### Step 1 — Push to GitHub (without secrets)
Your `.gitignore` already excludes `.env`, `data/`, and `.streamlit/secrets.toml`.
Only push these files:
```
app.py  config.py  auth.py  database.py
translator.py  payments.py  email_service.py
requirements.txt  .gitignore  .env.example
.streamlit/config.toml        ← safe, no secrets
Procfile  README.md
```

### Step 2 — Deploy on share.streamlit.io
1. Go to **share.streamlit.io** → sign in with GitHub
2. New app → select your repo → main file: `app.py`
3. Click **Advanced settings** → paste your secrets (see below)
4. Click **Deploy**

### Step 3 — Add secrets on Streamlit Cloud
In Advanced settings → Secrets, paste:
```toml
GROQ_API_KEY       = "gsk_your_key"
ADMIN_USERNAME     = "admin"
ADMIN_PASSWORD     = "YourPassword@123"
PORTPOS_SANDBOX    = "true"
PORTPOS_APP_KEY    = "your_portpos_sandbox_app_key"
PORTPOS_SECRET_KEY = "your_portpos_sandbox_secret_key"
APP_URL            = "https://your-app-name.streamlit.app"
EMAIL_ENABLED      = "false"
```

### Step 4 — Update APP_URL after deploy
After your app is live, Streamlit gives you a URL like:
`https://muhammad-bangla-translator-xxxx.streamlit.app`

Go back to Settings → Secrets → update `APP_URL` to your real URL → Save.
This is required for PortPos to redirect back correctly after payment.

---

## Get free PortPos sandbox keys

1. Go to **sandbox.portpos.com**
2. Click Register — email + password only, no docs needed
3. Log in → click your name (top right) → API Keys
4. Copy **App Key** and **Secret Key**
5. Paste into `.env` (local) or Streamlit secrets (deployed)

---

## API keys needed

| Key | Where to get | Cost |
|-----|-------------|------|
| GROQ_API_KEY | console.groq.com | Free forever |
| PORTPOS_APP_KEY | sandbox.portpos.com | Free sandbox |
| PORTPOS_SECRET_KEY | sandbox.portpos.com | Free sandbox |

---

## What's in the app

| Page | What it does |
|------|-------------|
| 🔤 Translate | Main translation with 7 domains, 4 tones, improve/explain/rate |
| 📋 History | Full searchable history, CSV export, bulk delete |
| ★ Favorites | Starred translations with folders and notes |
| 📊 Analytics | Daily charts, domain breakdown, hourly heatmap, streak |
| 💳 Pricing | Plan cards, coupon codes, PortPos payment, manual bKash |
| 👤 Profile | Edit name/email/avatar, change password, export data |
| 📜 Terms | Terms of service |
| 🔒 Privacy | Privacy policy |
| ⚙️ Admin | Revenue, coupons, users, emails, manual upgrade |

---

## Test payment in sandbox

On the Pricing page click any plan → click Pay → PortPos sandbox opens:

| Method | Details |
|--------|---------|
| Visa test card | `4111 1111 1111 1111` · any future expiry · any CVV |
| DBBL Nexus | `5200 0000 0000 0007` · 12/26 · 123 |
| bKash | Select on page, follow sandbox flow |

---

## Go live with PortPos (when ready)

1. Go to **manage.portpos.com** → Register
2. Upload NID (front + back) + bank account details
3. Get live keys in 1–3 business days
4. Update secrets: `PORTPOS_SANDBOX=false` + new keys + real `APP_URL`

No trade license needed. No annual fee. ~2% per transaction.
