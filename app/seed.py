"""Fill the database with fake students for the demo.

    python -m app.seed                   # 60 students, 60% newcomers
    python -m app.seed --n 100 --newcomers 0.7
    python -m app.seed --feedback        # fake feedback for the latest matching round
    python -m app.seed --clear           # remove all demo students again

Demo accounts use emails like demo017@study.thws.de and are easy to remove.
"""
import argparse
import json
import random
from datetime import datetime, timezone

from . import options
from .db import connect, init_db, new_lunch_id

DEMO_DOMAIN = "study.thws.de"
DEMO_PREFIX = "demo"

NEWCOMER_EXTRA_LANGS = ["hi", "hi", "es", "es", "ar", "tr", "zh", "uk", "ru", "fr", "it", "pt"]
# Rough share of students per Mensa (most THWS students eat at Hubland or in Schweinfurt).
MENSA_WEIGHTS = {"wue-hubland-sued": 35, "wue-studentenhaus": 20, "wue-roentgenring": 12,
                 "wue-josef-schneider": 8, "sw-thws": 25}
AGE_WEIGHTS = {"18-21": 35, "22-25": 40, "26-30": 20, "31+": 5}


def _slots(rng: random.Random) -> list[str]:
    # 12:30 is the busiest Mensa time; people pick 3-6 slots.
    weights = [1 if s.endswith("11:30") else 3 if s.endswith("12:30") else 2 for s in options.SLOTS]
    k = rng.randint(3, 6)
    chosen = set()
    while len(chosen) < k:
        chosen.add(rng.choices(options.SLOTS, weights)[0])
    return sorted(chosen, key=options.SLOTS.index)


def _profile(rng: random.Random, role: str) -> dict:
    if role == "newcomer":
        langs = {"en"} if rng.random() < 0.95 else set()
        langs.add(rng.choice(NEWCOMER_EXTRA_LANGS))
        if rng.random() < 0.35:
            langs.add("de")  # learning German
    else:
        langs = {"de"}
        if rng.random() < 0.9:
            langs.add("en")
        if rng.random() < 0.2:
            langs.add(rng.choice(["es", "fr", "it", "tr"]))
    mensa = rng.choices(list(MENSA_WEIGHTS), list(MENSA_WEIGHTS.values()))[0]
    # Ages 18-35, most in their early/mid twenties.
    age = min(options.AGE_MAX, max(options.AGE_MIN, round(rng.gauss(23, 3.5))))
    lo, hi = options.AGE_MIN, options.AGE_MAX  # most people don't mind
    if rng.random() < 0.25:
        lo, hi = max(options.AGE_MIN, age - rng.randint(3, 6)), min(options.AGE_MAX, age + rng.randint(3, 8))
    answered = rng.sample(options.THIS_OR_THAT, rng.randint(4, len(options.THIS_OR_THAT)))
    return {
        "role": role,
        "faculty": rng.choice(options.FACULTIES[:-1]),
        "languages": sorted(langs),
        "answers": {k: rng.choice([a, b]) for k, a, b in answered},
        "city": options.MENSA_CITY[mensa],
        "mensa": mensa,
        "slots": _slots(rng),
        "age": age,
        "age_min": lo,
        "age_max": hi,
    }


def clear() -> int:
    with connect() as conn:
        return conn.execute("DELETE FROM users WHERE email LIKE ?", (f"{DEMO_PREFIX}%@{DEMO_DOMAIN}",)).rowcount


def seed(n: int, newcomer_share: float, friend_pairs: int, rng_seed: int) -> None:
    rng = random.Random(rng_seed)
    clear()
    now = datetime.now(timezone.utc).isoformat()
    n_new = round(n * newcomer_share)
    roles = ["newcomer"] * n_new + ["local"] * (n - n_new)
    rng.shuffle(roles)
    emails = [f"{DEMO_PREFIX}{i:03d}@{DEMO_DOMAIN}" for i in range(1, n + 1)]
    profiles = [_profile(rng, r) for r in roles]

    # A few friends who registered together (same Mensa, overlapping times, no age limits).
    for i in range(min(friend_pairs, n // 2)):
        a, b = profiles[2 * i], profiles[2 * i + 1]
        b["city"], b["mensa"] = a["city"], a["mensa"]
        b["slots"] = sorted(set(b["slots"]) | {a["slots"][0]}, key=options.SLOTS.index)
        a["languages"] = sorted(set(a["languages"]) | {"en"})
        b["languages"] = sorted(set(b["languages"]) | {"en"})
        a["age_min"] = b["age_min"] = options.AGE_MIN
        a["age_max"] = b["age_max"] = options.AGE_MAX
        a["friend_email"], b["friend_email"] = emails[2 * i + 1], emails[2 * i]

    with connect() as conn:
        for email, p in zip(emails, profiles):
            uid = conn.execute("INSERT INTO users (email, lunch_id) VALUES (?, ?)",
                               (email, new_lunch_id(conn))).lastrowid
            conn.execute(
                """INSERT INTO profiles (user_id, role, faculty, languages, answers, city, mensa, slots,
                                         age, age_min, age_max, friend_email, consent_at, completed, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (uid, p["role"], p["faculty"], json.dumps(p["languages"]),
                 json.dumps(p["answers"], ensure_ascii=False), p["city"], p["mensa"],
                 json.dumps(p["slots"]), p["age"], p["age_min"], p["age_max"],
                 p.get("friend_email"), now, now),
            )
    print(f"Added {n} demo students ({n_new} newcomers, {n - n_new} locals, {friend_pairs} friend pairs).")


def fake_feedback(rng_seed: int) -> None:
    """Pretend the demo students had their lunch and ~70% answered the feedback."""
    rng = random.Random(rng_seed)
    with connect() as conn:
        r = conn.execute("SELECT id FROM match_rounds ORDER BY id DESC LIMIT 1").fetchone()
        if not r:
            print("Run the matching first (admin page), then add feedback.")
            return
        tables = conn.execute("SELECT id FROM match_tables WHERE round_id = ?", (r["id"],)).fetchall()
        n = 0
        for t in tables:
            seats = conn.execute(
                """SELECT s.user_id FROM match_seats s JOIN users u ON u.id = s.user_id
                   WHERE s.table_id = ? AND u.email LIKE ?""", (t["id"], f"{DEMO_PREFIX}%@{DEMO_DOMAIN}")
            ).fetchall()
            happy_table = rng.random() < 0.35  # some tables click and all want to stay in touch
            for s in seats:
                if rng.random() > 0.7 and not happy_table:
                    continue
                came = rng.random() < 0.85
                conn.execute(
                    """INSERT OR REPLACE INTO feedback (table_id, user_id, attended, rating, meet_again, join_again)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (t["id"], s["user_id"], "yes" if came else "no",
                     (rng.choice([4, 5, 5]) if happy_table else rng.choice([2, 3, 4, 4, 5])) if came else None,
                     ("yes" if happy_table else rng.choice(["yes", "no"])) if came else None,
                     rng.choice(["yes", "yes", "maybe", "no"]) if not happy_table else "yes"),
                )
                if came and rng.random() < 0.8:  # most who came also checked in with the table code
                    conn.execute("UPDATE match_seats SET checked_in_at = datetime('now') WHERE table_id = ? AND user_id = ?",
                                 (t["id"], s["user_id"]))
                n += 1
    print(f"Added feedback from {n} demo students for the latest round.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=60, help="number of demo students")
    ap.add_argument("--newcomers", type=float, default=0.6, help="share of newcomers, 0-1")
    ap.add_argument("--pairs", type=int, default=3, help="friend pairs")
    ap.add_argument("--seed", type=int, default=42, help="random seed (same seed = same students)")
    ap.add_argument("--clear", action="store_true", help="only remove demo students")
    ap.add_argument("--feedback", action="store_true", help="add fake feedback for the latest round")
    args = ap.parse_args()
    init_db()
    if args.clear:
        print(f"Removed {clear()} demo students.")
    elif args.feedback:
        fake_feedback(args.seed)
    else:
        seed(args.n, args.newcomers, args.pairs, args.seed)
