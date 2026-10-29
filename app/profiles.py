"""Lunch profile over three pages: validation, storage, and account deletion."""
import json
from datetime import datetime, timezone

from . import auth, options
from .db import connect

MIN_THIS_OR_THAT = 3
JSON_FIELDS = ("languages", "answers", "slots")

# Which columns each page owns, and the page order.
STEPS = {
    "about": ("role", "faculty", "languages", "answers"),
    "where": ("city", "mensa", "slots"),
    "prefs": ("age", "age_min", "age_max", "friend_email"),
}
STEP_ORDER = list(STEPS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_profile(user_id: int) -> dict | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return None
    p = dict(row)
    for f in JSON_FIELDS:
        p[f] = json.loads(p[f]) if p[f] else ([] if f != "answers" else {})
    return p


def step_done(p: dict | None, step: str) -> bool:
    if not p:
        return False
    required = {"about": "role", "where": "mensa", "prefs": "age"}[step]
    return p.get(required) is not None


def first_open_step(p: dict | None) -> str:
    for s in STEP_ORDER:
        if not step_done(p, s):
            return s
    return STEP_ORDER[0]


# ---------- page 1: about you ----------

def parse_about(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    role = form.get("role")
    if role not in options.ROLES:
        errors["role"] = "Pick one, so we can balance the table."
    faculty = form.get("faculty")
    if faculty not in options.FACULTIES:
        errors["faculty"] = "Pick your faculty (or Other)."
    valid_langs = {code for code, _ in options.LANGUAGES}
    languages = [l for l in form.getlist("languages") if l in valid_langs]
    if not languages:
        errors["languages"] = "Pick at least one language you're happy to chat in."
    answers = {}
    for key, a, b in options.THIS_OR_THAT:
        v = form.get(f"tot_{key}")
        if v in (a, b):
            answers[key] = v
    if len(answers) < MIN_THIS_OR_THAT:
        errors["answers"] = f"Pick at least {MIN_THIS_OR_THAT}. It helps us find things you have in common."
    return {"role": role, "faculty": faculty, "languages": languages, "answers": answers}, errors


# ---------- page 2: where & when ----------

def parse_where(form) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    city = form.get("city")
    if city not in options.MENSAS:
        errors["city"] = "Pick the city where you'd like to have lunch."
    mensa = form.get("mensa")
    if city in options.MENSAS and options.MENSA_CITY.get(mensa) != city:
        errors["mensa"] = f"Pick a Mensa in {city}."
        mensa = None
    valid_slots = set(options.SLOTS)
    slots = [s for s in form.getlist("slots") if s in valid_slots]
    if not slots:
        errors["slots"] = "Pick at least one lunch time."
    return {"city": city, "mensa": mensa, "slots": slots}, errors


# ---------- page 3: who you'd like to meet ----------

def parse_prefs(form, own_email: str) -> tuple[dict, dict]:
    errors: dict[str, str] = {}
    def num(name):
        try:
            return max(options.AGE_MIN, min(options.AGE_MAX, int(form.get(name, ""))))
        except ValueError:
            return None
    age = num("age")
    if age is None:
        errors["age"] = "Set your age on the slider."
    lo, hi = num("age_min"), num("age_max")
    lo = options.AGE_MIN if lo is None else lo
    hi = options.AGE_MAX if hi is None else hi
    if lo > hi:
        lo, hi = hi, lo  # handles dragged past each other

    friend_email = auth.normalize_email(form.get("friend_email") or "")
    if friend_email:
        err = auth.validate_email(friend_email)
        if err:
            errors["friend_email"] = err.replace("your university email", "their university email")
        elif friend_email == own_email:
            errors["friend_email"] = "That's your own email. Enter your friend's."
    if form.get("consent") != "yes":
        errors["consent"] = "We need your OK to use this information for matching."
    data = {"age": age, "age_min": lo, "age_max": hi, "friend_email": friend_email or None}
    return data, errors


def save_step(user_id: int, step: str, data: dict) -> None:
    cols = STEPS[step]
    values = [json.dumps(data[c], ensure_ascii=False) if c in JSON_FIELDS else data[c] for c in cols]
    extra_cols, extra_vals = ["updated_at"], [_now()]
    if step == "prefs":
        extra_cols += ["consent_at", "completed"]
        extra_vals += [_now(), 1]
    all_cols = list(cols) + extra_cols
    all_vals = values + extra_vals
    with connect() as conn:
        conn.execute("INSERT OR IGNORE INTO profiles (user_id) VALUES (?)", (user_id,))
        conn.execute(
            f"UPDATE profiles SET {', '.join(c + ' = ?' for c in all_cols)} WHERE user_id = ?",
            (*all_vals, user_id),
        )


def delete_account(user_id: int, email: str) -> None:
    """GDPR right to erasure: remove the user, their profile, seats, feedback and login tokens."""
    with connect() as conn:
        conn.execute("DELETE FROM login_tokens WHERE email = ?", (email,))
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))  # cascades to everything else
