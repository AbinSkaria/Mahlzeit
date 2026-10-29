"""Runs the matcher on every completed profile, stores the result, and
collects the optional after-lunch feedback."""
import hmac
import json
import os
import random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from . import icebreakers, matching, options, safety
from .db import connect, new_checkin_code


def load_profiles(for_matching: bool = False) -> list[dict]:
    """Completed profiles only (all three pages saved). For matching, people paused
    after reports are left out and everyone gets the list of people to avoid."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT p.*, u.email, u.lunch_id FROM profiles p JOIN users u ON u.id = p.user_id
               WHERE p.completed = 1 ORDER BY p.user_id"""
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        for f in ("languages", "slots"):
            d[f] = json.loads(d[f]) if d[f] else []
        d["answers"] = json.loads(d["answers"]) if d["answers"] else {}
        out.append(d)
    if for_matching:
        avoid = safety.avoid_pairs()
        paused = safety.paused_users()
        out = [p for p in out if p["user_id"] not in paused]
        for p in out:
            p["avoid"] = avoid.get(p["user_id"], set())
    return out


def run_round(seed: int | None = None) -> int:
    profiles = load_profiles(for_matching=True)
    prev = latest_round()
    priority = {p["email"] for p in prev["waitlist"]} if prev else set()
    result = matching.match(profiles, seed=seed, priority=priority)
    with connect() as conn:
        round_id = conn.execute("INSERT INTO match_rounds DEFAULT VALUES").lastrowid
        for t in result["tables"]:
            ice = icebreakers.for_table(options.MENSA_CITY.get(t["mensa"], ""), t["shared"])
            tid = conn.execute(
                """INSERT INTO match_tables (round_id, table_no, mensa, slot, score, languages, icebreakers, checkin_code)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (round_id, t["table_no"], t["mensa"], t["slot"], t["score"],
                 json.dumps(t["languages"]), json.dumps(ice, ensure_ascii=False), new_checkin_code()),
            ).lastrowid
            animals = random.sample([a for a, _, _ in options.ANIMALS], len(t["people"]))
            conn.executemany(
                "INSERT INTO match_seats (table_id, user_id, animal) VALUES (?, ?, ?)",
                [(tid, p["user_id"], a) for p, a in zip(t["people"], animals)],
            )
    return round_id


def latest_round() -> dict | None:
    """Latest round with its tables, people, feedback and waitlist, ready for templates."""
    with connect() as conn:
        r = conn.execute("SELECT * FROM match_rounds ORDER BY id DESC LIMIT 1").fetchone()
        if r is None:
            return None
        # Tables from before check-in codes existed get one now.
        for t in conn.execute("SELECT id FROM match_tables WHERE round_id = ? AND checkin_code IS NULL",
                              (r["id"],)).fetchall():
            conn.execute("UPDATE match_tables SET checkin_code = ? WHERE id = ?", (new_checkin_code(), t["id"]))
        tables = [dict(t) for t in conn.execute(
            "SELECT * FROM match_tables WHERE round_id = ? ORDER BY table_no", (r["id"],))]
        seats = conn.execute(
            """SELECT s.table_id, s.user_id, s.animal, s.checked_in_at, s.failed_checkins FROM match_seats s
               JOIN match_tables t ON t.id = s.table_id WHERE t.round_id = ?""", (r["id"],)
        ).fetchall()
        fb_rows = conn.execute(
            """SELECT f.* FROM feedback f JOIN match_tables t ON t.id = f.table_id
               WHERE t.round_id = ?""", (r["id"],)
        ).fetchall()
    profiles = {p["user_id"]: p for p in load_profiles()}
    by_table: dict[int, list] = {}
    for s in seats:
        if s["user_id"] in profiles:
            emoji, name = options.ANIMAL.get(s["animal"] or "", ("🍽️", "Guest"))
            by_table.setdefault(s["table_id"], []).append(
                {**profiles[s["user_id"]], "animal": s["animal"], "emoji": emoji, "animal_name": name,
                 "checked_in_at": s["checked_in_at"], "failed_checkins": s["failed_checkins"]})
    fb: dict[int, dict] = {}
    for f in fb_rows:
        fb.setdefault(f["table_id"], {})[f["user_id"]] = dict(f)

    seated_ids = set()
    for t in tables:
        t["people"] = sorted(by_table.get(t["id"], []), key=lambda p: p["role"] != "newcomer")
        t["languages"] = json.loads(t["languages"])
        t["icebreakers"] = json.loads(t["icebreakers"])
        t["feedback"] = fb.get(t["id"], {})
        t["city"] = options.MENSA_CITY.get(t["mensa"], "")
        # Everyone at the table said "yes, let's stay in touch" -> emails are shared.
        t["stay_in_touch"] = bool(t["people"]) and all(
            t["feedback"].get(p["user_id"], {}).get("meet_again") == "yes" for p in t["people"])
        seated_ids.update(p["user_id"] for p in t["people"])
    all_profiles = list(profiles.values())
    paused = safety.paused_users()
    waitlist = [
        {**p, "reason": "Paused after reports, waiting for the team's review" if p["user_id"] in paused
         else matching.waitlist_reason(p, all_profiles)}
        for p in all_profiles if p["user_id"] not in seated_ids
    ]
    return {"id": r["id"], "created_at": r["created_at"], "tables": tables, "waitlist": waitlist,
            "feedback_stats": feedback_stats(tables)}


def feedback_stats(tables: list[dict]) -> dict:
    """The challenge's success measures: show-up, return intent, lasting contact."""
    answers = [f for t in tables for f in t["feedback"].values()]
    att = [f["attended"] for f in answers if f["attended"]]
    ratings = [f["rating"] for f in answers if f["rating"]]
    join = [f["join_again"] for f in answers if f["join_again"]]
    seated = sum(len(t["people"]) for t in tables)
    checked_in = sum(1 for t in tables for p in t["people"] if p.get("checked_in_at"))
    return {
        "responses": len(answers),
        "seated": seated,
        "checked_in": checked_in,
        "verified_showed_up": round(100 * checked_in / seated) if seated else None,
        "showed_up": round(100 * att.count("yes") / len(att)) if att else None,
        "avg_rating": round(sum(ratings) / len(ratings), 1) if ratings else None,
        "join_again": round(100 * join.count("yes") / len(join)) if join else None,
        "tables_staying_in_touch": sum(t["stay_in_touch"] for t in tables),
    }


def save_feedback(table_id: int, user_id: int, data: dict) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO feedback (table_id, user_id, attended, rating, meet_again, join_again, comment)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(table_id, user_id) DO UPDATE SET
                 attended = excluded.attended, rating = excluded.rating,
                 meet_again = excluded.meet_again, join_again = excluded.join_again,
                 comment = excluded.comment, created_at = datetime('now')""",
            (table_id, user_id, data["attended"], data["rating"], data["meet_again"],
             data["join_again"], data["comment"]),
        )


MAX_FAILED_CHECKINS = 5
CHECKIN_BEFORE = timedelta(minutes=30)
CHECKIN_AFTER = timedelta(hours=2, minutes=30)


def _berlin_now() -> datetime:
    """Current time in Germany. Windows has no built-in time-zone data, so this needs
    the 'tzdata' package there; without it, fall back to the computer's own clock
    instead of crashing."""
    try:
        return datetime.now(ZoneInfo("Europe/Berlin"))
    except ZoneInfoNotFoundError:
        return datetime.now()


def checkin_window(slot: str, now: datetime | None = None) -> str | None:
    """None if check-in is open now, otherwise a message saying when it opens.
    Like a one-time password, the table code only works on the lunch day, from
    30 minutes before to 2.5 hours after the lunch time. Demo mode skips this so
    the prototype can be tried at any time."""
    if os.environ.get("MAHLZEIT_DEMO", "1") == "1":
        return None
    now = now or _berlin_now()
    day, time = slot.split("-")
    if now.weekday() > options.DAYS.index(day):
        return "Check-in for this lunch has closed."
    if now.weekday() < options.DAYS.index(day):
        return f"Check-in opens on the day of your lunch ({slot_label(slot)}), 30 minutes before."
    h, m = map(int, time.split(":"))
    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if now < start - CHECKIN_BEFORE:
        return f"Check-in opens at {(start - CHECKIN_BEFORE):%H:%M}, 30 minutes before your lunch."
    if now > start + CHECKIN_AFTER:
        return "Check-in for this lunch has closed."
    return None


def check_in(table: dict, user_id: int, code: str) -> str:
    """Returns 'ok', 'wrong', 'locked' or 'closed'. A correct code marks the person as
    verifiably present (and counts as 'I was there' for the feedback). The code only
    works for this week's table: a new matching round gives every table a new code."""
    me = next(p for p in table["people"] if p["user_id"] == user_id)
    if me.get("checked_in_at"):
        return "ok"
    if me.get("failed_checkins", 0) >= MAX_FAILED_CHECKINS:
        return "locked"
    if checkin_window(table["slot"]):
        return "closed"
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    with connect() as conn:
        # constant-time comparison, so the code can't be worked out digit by digit
        if code and table.get("checkin_code") and hmac.compare_digest(code, table["checkin_code"]):
            conn.execute("UPDATE match_seats SET checked_in_at = datetime('now') WHERE table_id = ? AND user_id = ?",
                         (table["id"], user_id))
            conn.execute(
                """INSERT INTO feedback (table_id, user_id, attended) VALUES (?, ?, 'yes')
                   ON CONFLICT(table_id, user_id) DO UPDATE SET attended = 'yes'""",
                (table["id"], user_id))
            return "ok"
        conn.execute("UPDATE match_seats SET failed_checkins = failed_checkins + 1 WHERE table_id = ? AND user_id = ?",
                     (table["id"], user_id))
    return "locked" if me.get("failed_checkins", 0) + 1 >= MAX_FAILED_CHECKINS else "wrong"


def mark_attended(table_id: int, user_id: int, attended: str) -> None:
    """The "I'm done with lunch" / "I couldn't make it" buttons on the home page."""
    with connect() as conn:
        conn.execute(
            """INSERT INTO feedback (table_id, user_id, attended) VALUES (?, ?, ?)
               ON CONFLICT(table_id, user_id) DO UPDATE SET attended = excluded.attended""",
            (table_id, user_id, attended),
        )


def parse_feedback(form) -> dict:
    """Every field is optional; anything invalid is simply treated as not answered."""
    def pick(name, allowed):
        v = form.get(name)
        return v if v in allowed else None
    rating = form.get("rating")
    comment = (form.get("comment") or "").strip()[:500] or None
    return {
        "attended": pick("attended", ("yes", "no")),
        "rating": int(rating) if rating in ("1", "2", "3", "4", "5") else None,
        "meet_again": pick("meet_again", ("yes", "no")),
        "join_again": pick("join_again", ("yes", "maybe", "no")),
        "comment": comment,
    }


def slot_label(slot: str) -> str:
    day, time = slot.split("-")
    names = dict(zip(options.DAYS, ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]))
    return f"{names.get(day, day)}, {time}"
