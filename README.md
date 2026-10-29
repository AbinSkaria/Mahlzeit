# 🍽️ Table for Four – Blind Lunch

> Turning a shared lunch into a lasting friendship: AI-assisted matching of international and German students in groups of four.

Built for the **THWS Fit4Germany** challenge *"Table for Four: how AI can turn a shared lunch into a lasting friendship (Blind Lunch)"* at Technische Hochschule Würzburg-Schweinfurt (THWS).

---

## 📌 The Challenge

Many international students want more support making contact with German students and settling into a new environment, especially in their first semester. There are few low-threshold formats that actively bring people together. The real bottleneck is the German side: German students usually already have a social circle and no obvious reason to take part. Without them, no matching can work.

We therefore need a format that appeals to **both sides** and **does not feel like volunteering**.

## 🎯 The Goal

Bring international and German students together **over lunch, in groups of four**, using a simple digital matching structure based on:

- 🗣️ Language preference
- 📚 Subject and campus
- 🎨 Shared interests
- 🕐 Available time slots

**Success means:**

- A balanced ratio of international and German sign-ups
- People actually showing up
- People coming back for more lunches
- Contacts that last beyond the meal

## ✨ Our Solution

*Blind Lunch* is a lightweight web-based matching tool. Students answer a few playful questions, and the system forms balanced tables of four (ideally 2 international + 2 German students) who share a time slot, a campus, and some common ground. The group only learns who they are sitting with shortly before the lunch, which keeps it fun and low-pressure.

### Key Features

- **Sign-up in under 2 minutes**: a few fields, no app installation, no account creation
- **Playful questionnaire**: interests collected through fun, low-effort questions instead of a boring form
- **Smart matching**: groups of four balanced by origin, language, subject, campus, interests, and availability
- **Blind reveal**: names and a meeting point are revealed shortly before the lunch
- **Follow-up nudge**: an optional message after the lunch to encourage staying in touch and signing up again
- **Admin overview**: simple view for the organisers to monitor the international/German ratio and show-up rates

## 🔒 Requirements Addressed

| Requirement | How we address it |
|---|---|
| Usable at a Bavarian university | Designed for THWS campuses (Würzburg and Schweinfurt) |
| DSGVO / GDPR compliant | Data minimisation, explicit consent, EU-hosted storage, deletion after the event cycle |
| Free or low-cost | Built on open-source tools and free tiers |
| Easy to maintain | Small codebase, minimal dependencies, documented setup |
| Low-threshold sign-up | Few fields, a few minutes, no registration or app install |

## 🏗️ How It Works

```
Sign-up form  →  Matching engine  →  Group of four  →  Blind reveal  →  Lunch  →  Follow-up
```

1. **Sign up**: the student picks a time slot and answers a few short questions.
2. **Match**: the matching engine builds balanced groups of four.
3. **Reveal**: each group receives the time, place, and first names shortly before the lunch.
4. **Meet**: lunch at the canteen or a nearby spot.
5. **Stay in touch**: optional feedback and a nudge to join the next round.

## 🧰 Tech Stack

- **Frontend:** server-rendered HTML pages (Jinja2) + one CSS file, mobile-first, no external fonts, scripts or trackers (GDPR)
- **Backend / matching:** Python 3, FastAPI; matching algorithm in plain Python (`app/matching.py`)
- **Storage:** SQLite (one file, `mahlzeit.db`), on a university server in production
- **Login & notifications:** passwordless email sign-in link via the university SMTP server (demo mode shows the link on screen)

## 🚀 Getting Started

```bash
git clone https://github.com/AbinSkaria/Challenge_7.git
cd Challenge_7
python -m venv .venv
.venv\Scripts\activate            # Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed                 # optional: 60 fake demo students
uvicorn app.main:app --reload      # then open http://localhost:8000
```

To allow Gmail addresses for testing, create a file `.env` (it is never uploaded) with
`MAHLZEIT_ALLOWED_DOMAINS=thws.de,gmail.com` and start with `uvicorn app.main:app --reload --env-file .env`.
Details are in the technical documentation below.

## 📁 Project Structure

```
.
├── README.md
├── requirements.txt       # Python packages
├── .env.example           # settings template (copy to .env, never upload .env)
└── app/
    ├── main.py            # all web pages and actions (routes)
    ├── matching.py        # the matching algorithm
    ├── rounds.py          # matching rounds, table animals, check-in codes, feedback stats
    ├── safety.py          # anonymous reports
    ├── profiles.py        # the 3 profile pages
    ├── auth.py            # email-link login, Lunch IDs
    ├── db.py              # database tables
    ├── options.py         # Mensas, faculties, languages, ages, this-or-that
    ├── icebreakers.py     # conversation starters
    ├── seed.py            # fake demo data (no real personal data)
    ├── mailer.py          # login emails
    ├── templates/         # HTML pages
    └── static/style.css   # design
```

## 🛡️ Data Protection

- Only the data necessary for matching is collected
- Participation is based on explicit, informed consent
- No sensitive personal data is requested
- Data is stored within the EU and deleted after the event cycle
- Participants can request deletion of their data at any time

## 📊 Measuring Success

- Ratio of international to German sign-ups
- Show-up rate per lunch
- Return rate (participants joining a second lunch)
- Share of participants still in contact after four weeks (follow-up survey)

## 🗺️ Roadmap

- [x] Sign-up form prototype (email-link login + 3-page profile)
- [x] Matching algorithm (v1)
- [x] Admin dashboard (registration balance, tables, check-ins, feedback, reports)
- [x] Check-in at the Mensa with a table code + anonymous reporting
- [ ] Blind reveal notifications (table emails before the lunch)
- [ ] Pilot lunch at one campus
- [ ] Feedback and follow-up loop
- [ ] Roll-out to further campuses

## 👥 Team

_Add team members here._

## 🔗 Links

- Challenge: THWS Fit4Germany – *Table for Four*
- Challenge video: https://www.youtube.com/watch?v=NLNt_KT6Kww

## 📄 License

_Choose a license (e.g. MIT) and add a `LICENSE` file._

---

# Technical documentation

The app is called **Mahlzeit!** (German lunchtime greeting, roughly "enjoy your meal").

Lunch for four: two students new to Germany, two locals. Hackathon prototype.

## Run it locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000.

- `python -m venv .venv` creates an isolated Python environment for this project, so its packages don't clash with others on your laptop.
- `activate` switches your terminal into that environment.
- `uvicorn ... --reload` starts the web server and restarts it automatically whenever you save a file.

**Demo mode** (default): no mail server is needed. After you enter an email, the "Check your inbox" page shows the sign-in link as a button, and the link is also printed in the terminal.

Only university emails are accepted. The default allows `@thws.de` and any subdomain such as `@study.thws.de`. Change it with `MAHLZEIT_ALLOWED_DOMAINS` (see `.env.example`). For testing with any address, temporarily set `MAHLZEIT_ALLOWED_DOMAINS=thws.de,gmail.com`.

## How login works

Passwordless "magic link":

1. Student enters their university email on `/login`.
2. The server creates a random one-time token, stores only its SHA-256 hash, and emails a link `/auth/verify?token=...`.
3. Clicking the link (valid 15 minutes, single use) logs them in. The first login creates the account, so registration and login are the same step.
4. A signed session cookie keeps them logged in for 30 days.

Why: no passwords to store, reset or leak; the email domain proves they're a THWS student; nothing to install.

## Project layout

```
app/
  main.py        routes: /, /login, /auth/verify, /home, /profile/{about,where,prefs}, /checkin, /badge, /lunch/done, /feedback, /report, /admin, /admin/cards, /logout, /privacy
  auth.py        email validation, token creation/checking, throttling
  db.py          SQLite schema (users, login_tokens, profiles, matching rounds, feedback, reports) — one file, no DB server
  profiles.py    profile validation, saving, account deletion
  options.py     form choices: campuses, faculties, languages, slots, this-or-that
  matching.py    the matching algorithm (works on plain dicts, so also on CSV data)
  icebreakers.py conversation starters per table
  rounds.py      runs + stores matching rounds (table animals, check-in codes), check-in, feedback and stats
  safety.py      anonymous reports, never-again pairs, pausing, logged reveals
  seed.py        demo data generator
  mailer.py      SMTP sending; prints the link instead in demo mode
  templates/     Jinja2 HTML pages
  static/        style.css (no external fonts or scripts, for GDPR)
```

## Production checklist

- Set `MAHLZEIT_SECRET` to a long random string (otherwise everyone is logged out on restart).
- Set `MAHLZEIT_DEMO=0` and configure `SMTP_*` with the university mail server.
- Set `MAHLZEIT_HTTPS=1` behind HTTPS.
- Confirm the student email domain with THWS IT.
- Have the data protection officer review `/privacy` (currently a draft).


## What students fill in

No names: every account gets a random **Lunch ID** (e.g. `#K7P2QX`), and tablemates see only that.

1. **About you** (`/profile/about`): new to Germany or local, faculty, languages, this-or-that picks (at least 3)
2. **Where & when** (`/profile/where`): city, then a Mensa in that city, then lunch time slots
3. **Who you'd like to meet** (`/profile/prefs`): age slider, age-range slider with two handles (full range = any),
   friend's email (optional), consent
4. **After the lunch** (on `/home`): "I'm done with lunch" / "I couldn't make it", then optional
   **feedback** (`/feedback`): rating, stay in touch with the table, join another lunch, comment.
   If everyone at a table says "stay in touch", their emails are shared with each other.

At each table everyone also gets an **animal** (🦊 Fox, 🐢 Turtle, …), unique within the table, so people
can say "I'm the Fox" instead of a name or a code.

## Check-in at the Mensa with the table code

- Each table gets a 4-digit code when the matching runs. Admin → **Print table cards** prints one card per
  table (number, Mensa, time, code) to put on the tables, so the code is only visible at the Mensa.
- On **My lunches**, the student types the code. If it's right, the phone shows a **badge**: "✓ Code accepted",
  their animal in big letters, and which animals at the table have arrived (refreshes by itself). They hold it
  up so everyone knows who is who.
- Like a one-time password: only valid for this week's table (new round = new codes), only on the lunch day
  from 30 minutes before to 2.5 hours after the lunch time (skipped in demo mode), and 5 wrong tries lock it.
- A check-in counts as **verified attendance**; the admin page shows it next to the self-reported show-up rate.

## Reporting without giving up anonymity (`/report`, `app/safety.py`)

- On the feedback page (question 6) or at `/report`: pick the tablemate by their animal (or "I'm not sure who"),
  a category, and optionally what happened.
- The reported person is never told who reported them. The team sees Lunch IDs and animals only.
- Automatic: a reported pair is never seated together again; someone reported by 2+ different people
  is paused from matching until the team resolves the reports.
- The team can reveal the emails behind a report; every reveal is logged (who, when). The reporter's
  email is only revealed if they ticked "you may contact me".

Edit the choices (Mensas, faculties, languages, age range, this-or-that) in `app/options.py`.
"Delete my account and data" on `/home` removes everything for that user immediately (GDPR right to erasure).

## Matching and the admin page

```bash
python -m app.seed                       # add 60 fake students (60% newcomers) for the demo
python -m app.seed --n 100 --newcomers 0.7
python -m app.seed --feedback            # fake feedback for the latest round (after matching)
python -m app.seed --clear               # remove the fake students again
```

Then open http://localhost:8000/admin and click **Run matching**. Students see their table,
time, tablemates and conversation starters on `/home`.

- `app/matching.py` — the algorithm. Hard rules: same Mensa, a shared lunch slot, a shared
  language, everyone within each other's age preferences, at least one newcomer and one local, friends together. Score: 2+2 balance, shared
  this-or-that picks, faculty mix. Tables are built around the scarce group (usually locals),
  filled with 2+2 first and 3+1 only for whoever is left, then repaired (a waiting local can
  turn a 3+1 table into 2+2) and improved with swaps.
- `app/icebreakers.py` — conversation starters from the group's shared picks (templates, no external AI).
- `app/rounds.py` — runs the matcher on the database and stores each round. People on the
  waitlist are placed first in the next round.
- Admin access: set `MAHLZEIT_ADMINS=you@example.com,colleague@example.com`. If it's empty in
  demo mode, every logged-in user can open `/admin`.

## Next

- Emails with the table number + "I'm coming / can't make it" buttons
- Blind reveal: show tablemates only shortly before the lunch
