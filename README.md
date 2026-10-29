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

> ✏️ *Adjust this section to match your final implementation.*

- **Frontend:** _e.g. static web form / HTML + JavaScript_
- **Backend / matching:** _e.g. Python_
- **Storage:** _e.g. EU-hosted database or spreadsheet_
- **Notifications:** _e.g. e-mail via university SMTP_

## 🚀 Getting Started

```bash
# Clone the repository
git clone https://github.com/<your-username>/<your-repo>.git
cd <your-repo>

# Install dependencies
# (replace with your actual setup)
pip install -r requirements.txt

# Run the matching script
python match.py
```

## 📁 Project Structure

> ✏️ *Update to reflect your actual layout.*

```
.
├── README.md
├── docs/              # Concept, privacy notes, presentation
├── src/               # Matching logic and application code
├── data/              # Sample / anonymised test data (no real personal data!)
└── LICENSE
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

- [ ] Sign-up form prototype
- [ ] Matching algorithm (v1)
- [ ] Blind reveal notifications
- [ ] Admin dashboard
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
