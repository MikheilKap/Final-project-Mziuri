# SubTracker

**EN** | [ქართული](#ქართული)

---

## English

A full-stack subscription management web app built with **FastAPI** and **Jinja2**. SubTracker connects to your Gmail, scans for active recurring subscriptions using AI, and gives you a live dashboard with spending analytics, renewal countdowns, and 3-day expiry alerts.

### Features

- **Gmail Scanner** — OAuth 2.0 Gmail integration; fetches recent emails and runs them through an AI filter (Groq / LLaMA 3.3) to detect active paid subscriptions. Trials, cancellations, refunds, and failed payments are automatically excluded.
- **AI Analysis** — LLM-powered extraction of service name, price, billing cycle, and next renewal date from email bodies. Falls back to rule-based parsing when the AI response is unusable.
- **Dashboard** — Live subscription cards showing cost, cycle, renewal date, and days remaining. Stale entries can be removed with one click.
- **3-Day Expiry Alerts** — Banner warnings and amber card highlights appear automatically when a renewal is ≤ 3 days away.
- **Spending Analytics** — Monthly spend, annual projection, active subscription count, most expensive service, and a doughnut chart breaking down cost per service.
- **Insights Panel** — Auto-generated plain-English summaries ("Adobe Creative Cloud costs you $239.88/year", "Your subscriptions will cost ~$948 this year").
- **Historical Storage** — Every scan snapshot is recorded in `subscription_history` for future trend analysis.
- **Manual Add/Remove** — Add subscriptions via a multi-step wizard; remove any entry from the dashboard.
- **User Accounts** — Sign-up, login, session management, password change, and avatar picker.
- **AI Assistant (FAB)** — Floating button opens a chat that gives step-by-step cancellation instructions for any service.

### Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn |
| Templates | Jinja2 |
| Database | SQLite via aiosqlite |
| AI / LLM | Groq API (`llama-3.3-70b-versatile`) |
| Gmail | Google OAuth 2.0, Gmail API v1 |
| Frontend | Bootstrap 5, Chart.js 4 |

### Requirements

- Python 3.10 or newer
- [Groq](https://console.groq.com/) account and API key
- Google Cloud project with **Gmail API** enabled and OAuth 2.0 credentials

### Installation

```bash
cd Final-project-Mziuri-main
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt
```

### Configuration

Copy the example env file and fill in your keys:

```bash
copy .env.example .env       # Windows
# cp .env.example .env       # macOS / Linux
```

`.env` variables:

```
API_KEY=gsk_xxxxxxxxxxxxxxxx          # Groq API key
SECRET_KEY=any-random-string          # Session secret
GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxx
OAUTH_REDIRECT_URI=http://127.0.0.1:8000/scanner/callback
```

> **Important:** `.env` is already in `.gitignore`. Never commit it or share API keys.

### Running

```bash
py -m uvicorn main:app --reload
```

App runs at: [http://127.0.0.1:8000](http://127.0.0.1:8000)
Interactive API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### Setting up Gmail OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create or select a project.
2. **APIs & Services → Library** → search "Gmail API" → **Enable**.
3. **APIs & Services → OAuth consent screen** → External → fill in app name → add your Google account as a test user.
4. **APIs & Services → Credentials** → Create credentials → OAuth client ID → Web application.
5. Add `http://127.0.0.1:8000/scanner/callback` as an **Authorized redirect URI**.
6. Copy the Client ID and Client Secret into your `.env`.

### Project Structure

```
Final-project-Mziuri-main/
├── main.py                      # FastAPI app, routes, Jinja2 filters
├── config/
│   └── settings.py              # Environment variables
├── routes/
│   ├── ai_routes.py             # AI assistant endpoint
│   └── scanner_routes.py        # Gmail OAuth + scan endpoints
├── services/
│   ├── email_analyzer.py        # Pre-filter, AI analysis, rule-based fallback
│   ├── groq_service.py          # Groq API wrapper
│   ├── prompt_service.py        # Prompt builder
│   ├── formatter.py             # Response formatter
│   └── markdown_utils.py        # Markdown helpers
├── database/
│   ├── db_config.py             # Schema init + migrations
│   ├── subscriptions.py         # Upsert + history recording
│   ├── auth.py                  # Session helpers
│   ├── avatars.py               # Avatar definitions
│   └── template_context.py      # Shared Jinja2 context builder
├── templates/                   # Jinja2 HTML templates
├── static/                      # CSS, JS, avatar images
├── subtracker.db                # SQLite database (auto-created)
├── requirements.txt
└── .env.example
```

### Security Notes

- Do not publish `API_KEY`, `SECRET_KEY`, or OAuth credentials in any repository.
- The app has no rate limiting by default — add middleware before exposing it to the public internet.
- Every Groq request consumes your quota; the scanner fetches at most 50 emails per run.

---

## ქართული

FastAPI-სა და Jinja2-ზე დაფუძნებული სრული გამოწერების მართვის ვებ-აპლიკაცია. SubTracker Gmail-ს უკავშირდება, AI-ის დახმარებით ამოიცნობს აქტიურ, განმეორებად გამოწერებს და გიჩვენებს ცოცხალ დეშბორდს ხარჯების ანალიტიკით, განახლების მოლოდინ-ტაიმერებითა და 3-დღიანი გაფრთხილებებით.

### ფუნქციები

- **Gmail სკანერი** — OAuth 2.0 Gmail ინტეგრაცია; ამოიღებს ბოლო ელ. ფოსტებს და AI-ის (Groq / LLaMA 3.3) საშუალებით ამოიცნობს აქტიურ, ფასიან გამოწერებს. სატესტო პერიოდები, გაუქმებები, თანხის დაბრუნება და წარუმატებელი გადახდები ავტომატურად გამოირიცხება.
- **AI ანალიზი** — LLM-ით ამოღება: სერვისის სახელი, ფასი, ბილინგის ციკლი და შემდეგი განახლების თარიღი. AI-ის წარუმატებლობის შემთხვევაში გამოიყენება წესებზე დაფუძნებული fallback.
- **დეშბორდი** — გამოწერების ბარათები: ფასი, ციკლი, განახლების თარიღი, დარჩენილი დღეები. ერთი დაჭერით შეიძლება ჩანაწერის წაშლა.
- **3-დღიანი გაფრთხილება** — ბანერი და ბარათის ქარვისფერი მონიშვნა ავტომატურად ჩნდება, როცა განახლება ≤ 3 დღეშია.
- **ხარჯების ანალიტიკა** — თვიური ხარჯი, წლიური პროგნოზი, გამოწერების რაოდენობა, ყველაზე ძვირი სერვისი და დოუნათ-დიაგრამა.
- **Insights პანელი** — ავტომატურად გენერირებული შეჯამებები ("Adobe Creative Cloud-ი ღირს $239.88/წელი" და ა.შ.).
- **ისტორიული შენახვა** — სკანირების ყოველი სნეფშოთი იწერება `subscription_history` ცხრილში.
- **ხელით დამატება/წაშლა** — მრავალსაფეხურიანი wizard-ით გამოწერის დამატება; წაშლა დეშბორდიდან.
- **მომხმარებლის ანგარიში** — რეგისტრაცია, შესვლა, სესიის მართვა, პაროლის შეცვლა, ავატარის არჩევა.
- **AI ასისტენტი** — მცურავი ღილაკი ხსნის ჩატს, რომელიც ნაბიჯ-ნაბიჯ გვიხსნის ნებისმიერი სერვისის გაუქმების პროცედურას.

### გაშვება

```bash
py -m uvicorn main:app --reload
```

სერვერი: [http://127.0.0.1:8000](http://127.0.0.1:8000)

### კონფიგურაცია

`.env` ფაილში ჩაწერეთ:

```
API_KEY=gsk_xxxxxxxxxxxxxxxx
SECRET_KEY=ნებისმიერი-სტრინგი
GOOGLE_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-xxxxxxxx
OAUTH_REDIRECT_URI=http://127.0.0.1:8000/scanner/callback
```

### უსაფრთხოება

- `API_KEY`, `SECRET_KEY` და OAuth გასაღებები არ გამოაქვეყნოთ GitHub-ზე.
- `.env` უკვე `.gitignore`-შია.
- გასაღების გაჟონვის შემთხვევაში დაუყოვნებლივ შეცვალეთ Groq Console-სა და Google Cloud Console-ში.
