"""Group matching: turns lunch profiles into tables of four.

Works on plain dicts, so it runs on the web app's database or on a CSV export
from any survey tool. No external libraries.

Hard rules (a table is only allowed if all hold):
  - everyone chose the same Mensa
  - everyone shares at least one lunch slot
  - everyone shares at least one language
  - at least one newcomer and at least one local (ideal: 2 + 2)
  - friends who registered together sit together
  - people who reported each other are never seated together again

Soft score (higher is better):
  - 2 newcomers + 2 locals                       +10   (3 + 1: +4)
  - each pair of people with the same this-or-that pick  +1
  - each different faculty at the table          +0.5

Method: locals are usually the scarce group and every table needs one, so each
table is started from one person of the scarce group. All tables are then filled
round-robin with the best-fitting people, preferring 2+2. Finally, random swaps
are kept only if the total score goes up. Fast enough for a few thousand people.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from itertools import combinations

from . import options

TABLE_SIZE = 4
MIN_TABLE_SIZE = 3          # a table of 3 is OK if 4 is impossible
SWAP_ITERATIONS = 3000

BALANCE_IDEAL = 10.0
BALANCE_OK = 4.0
SHARED_PICK = 1.0
FACULTY_MIX = 0.5


@dataclass
class Unit:
    """One person, or two friends who must sit together."""
    people: list[dict]

    @property
    def size(self) -> int:
        return len(self.people)

    @property
    def mensa(self) -> str:
        return self.people[0]["mensa"]

    def count(self, role: str) -> int:
        return sum(p["role"] == role for p in self.people)


@dataclass
class Table:
    units: list[Unit] = field(default_factory=list)

    @property
    def people(self) -> list[dict]:
        return [p for u in self.units for p in u.people]

    @property
    def size(self) -> int:
        return sum(u.size for u in self.units)

    def count(self, role: str) -> int:
        return sum(u.count(role) for u in self.units)


# ---------- helpers ----------

def common(people: list[dict], key: str) -> set:
    sets = [set(p[key]) for p in people]
    return set.intersection(*sets) if sets else set()


def _in_range(age, lo, hi) -> bool:
    if age is None:
        return True
    lo = options.AGE_MIN if lo is None else lo
    hi = options.AGE_MAX if hi is None else hi
    return lo <= age and (age <= hi or hi >= options.AGE_MAX)


def age_ok(a: dict, b: dict) -> bool:
    """Each person's age must be inside the other's preferred range."""
    return (_in_range(b.get("age"), a.get("age_min"), a.get("age_max")) and
            _in_range(a.get("age"), b.get("age_min"), b.get("age_max")))


def compatible(people: list[dict]) -> bool:
    """Mensa, slot, language and age rules (role balance is checked separately)."""
    if len({p["mensa"] for p in people}) > 1:
        return False
    if not (common(people, "slots") and common(people, "languages")):
        return False
    for a, b in combinations(people, 2):
        # Someone who reported the other (or was reported) is never seated with them again.
        if b.get("user_id") in a.get("avoid", ()) or a.get("user_id") in b.get("avoid", ()):
            return False
        if not age_ok(a, b):
            return False
    return True


def balanced(people: list[dict]) -> bool:
    roles = [p["role"] for p in people]
    return "newcomer" in roles and "local" in roles


def score(people: list[dict]) -> float:
    n = sum(p["role"] == "newcomer" for p in people)
    l = len(people) - n
    s = 0.0
    if n == 2 and l == 2:
        s += BALANCE_IDEAL
    elif n >= 1 and l >= 1:
        s += BALANCE_OK
    for a, b in combinations(people, 2):
        for k, v in a["answers"].items():
            if b["answers"].get(k) == v:
                s += SHARED_PICK
    s += FACULTY_MIX * len({p["faculty"] for p in people})
    return s


def pick_slot(people: list[dict]) -> str:
    """Earliest shared slot in week order (Mon 11:30 first)."""
    shared = common(people, "slots")
    return min(shared, key=options.SLOTS.index)


def shared_picks(people: list[dict]) -> list[tuple[str, str, int]]:
    """(question key, answer, how many chose it) for answers 3+ people share."""
    out = []
    for key, a, b in options.THIS_OR_THAT:
        for ans in (a, b):
            n = sum(p["answers"].get(key) == ans for p in people)
            if n >= 3:
                out.append((key, ans, n))
    out.sort(key=lambda x: -x[2])
    return out


# ---------- building units (friend pairs) ----------

def build_units(profiles: list[dict]) -> list[Unit]:
    by_email = {p["email"]: p for p in profiles}
    used: set[str] = set()
    units: list[Unit] = []
    for p in profiles:
        if p["email"] in used:
            continue
        f = by_email.get(p.get("friend_email") or "")
        # Only a *mutual* friend link that can actually share a table counts.
        if (f and f["email"] not in used and f.get("friend_email") == p["email"]
                and compatible([p, f])):
            units.append(Unit([p, f]))
            used.update({p["email"], f["email"]})
        else:
            units.append(Unit([p]))
            used.add(p["email"])
    return units


# ---------- table construction ----------

def _fits(t_people: list[dict], u: Unit, scarce: str, max_other: int = 3) -> bool:
    people = t_people + u.people
    if len(people) > TABLE_SIZE or not compatible(people):
        return False
    n_scarce = sum(p["role"] == scarce for p in people)
    n_other = len(people) - n_scarce
    # Never more than 2 of the scarce role at one table (they're needed elsewhere).
    # max_other=2 builds only 2+2 tables; max_other=3 also allows 3+1.
    return n_scarce <= 2 and n_other <= max_other


def _gain(t_people: list[dict], u: Unit, priority: set[str]) -> float:
    people = t_people + u.people
    n = sum(p["role"] == "newcomer" for p in people)
    g = score(people) - score(t_people)
    if n <= 2 and len(people) - n <= 2:
        g += 5                      # keeps a 2+2 table reachable
    if any(p["email"] in priority for p in u.people):
        g += 8                      # waitlisted last round: seat them first
    # People with few lunch slots get fewer chances later, so place them early.
    g += 2.0 / len(common(u.people, "slots"))
    return g


def _build_tables(units: list[Unit], rng: random.Random,
                  priority: set[str]) -> tuple[list[Table], list[Unit]]:
    """Every table needs at least one person of the scarce role (usually locals),
    so tables are built around them: one scarce person seeds each table, then all
    tables are filled round-robin so no table grabs all the good matches."""
    if not units:
        return [], []
    newcomers = sum(u.count("newcomer") for u in units)
    locals_ = sum(u.count("local") for u in units)
    scarce = "local" if locals_ <= newcomers else "newcomer"
    total = newcomers + locals_

    def hardness(u: Unit):
        return (not any(p["email"] in priority for p in u.people),
                len(common(u.people, "slots")), len(common(u.people, "languages")), rng.random())

    scarce_units = sorted([u for u in units if u.count(scarce)], key=hardness)
    others = [u for u in units if not u.count(scarce)]

    # As many tables as can be filled to ~4, but never more than there are scarce people.
    n_tables = min(len(scarce_units), -(-total // TABLE_SIZE))
    tables = [Table([u]) for u in scarce_units[:n_tables]]
    pool = scarce_units[n_tables:] + others

    def fill(tables: list[Table], pool: list[Unit], max_other: int = 3) -> None:
        changed = True
        while changed and pool:
            changed = False
            for t in sorted(tables, key=lambda t: t.size):
                if t.size >= TABLE_SIZE:
                    continue
                cands = [u for u in pool if _fits(t.people, u, scarce, max_other)]
                if not cands:
                    continue
                best = max(cands, key=lambda u: _gain(t.people, u, priority))
                t.units.append(best)
                pool.remove(best)
                changed = True

    fill(tables, pool, max_other=2)   # first: only ideal 2+2 tables
    fill(tables, pool, max_other=3)   # then: 3+1 for whoever is left

    # Tables that ended up too small or one-sided are dissolved and retried.
    kept, leftover = [], list(pool)
    for t in tables:
        if t.size >= MIN_TABLE_SIZE and balanced(t.people):
            kept.append(t)
        else:
            leftover.extend(t.units)
    fill(kept, leftover)

    _repair(kept, leftover, scarce, hardness, fill)
    return kept, leftover


def _repair(tables: list[Table], leftover: list[Unit], scarce: str, hardness, fill) -> None:
    """Repeat three fixes until nothing changes:
    1. put waiting people into tables that still have a free seat;
    2. a waiting scarce person (usually a local) swaps in for someone at a 3+1 table,
       turning it into 2+2; the person swapped out goes back to the waiting list;
    3. start new tables from waiting scarce people.
    Fix 2 always creates one more 2+2 table, so the loop is guaranteed to end."""
    changed = True
    while changed:
        changed = False

        # 1. free seats
        for u in sorted(leftover, key=hardness):
            t = next((t for t in sorted(tables, key=lambda t: t.size)
                      if _fits(t.people, u, scarce)), None)
            if t:
                t.units.append(u)
                leftover.remove(u)
                changed = True

        # 2. waiting scarce person upgrades a 3+1 table to 2+2
        for u in [u for u in leftover if u.size == 1 and u.count(scarce)]:
            for t in tables:
                if t.size != TABLE_SIZE or t.count(scarce) != 1:
                    continue
                out = next((v for v in t.units if v.size == 1 and not v.count(scarce)
                            and compatible([p for w in t.units if w is not v for p in w.people] + u.people)),
                           None)
                if out:
                    t.units = [w for w in t.units if w is not out] + [u]
                    leftover.remove(u)
                    leftover.append(out)
                    changed = True
                    break

        # 3. new tables from whoever is still waiting
        for seed_unit in sorted([u for u in leftover if u.count(scarce)], key=hardness):
            if seed_unit not in leftover:
                continue
            leftover.remove(seed_unit)
            t = Table([seed_unit])
            fill([t], leftover)
            if t.size >= MIN_TABLE_SIZE and balanced(t.people):
                tables.append(t)
                changed = True
            else:
                leftover.extend(t.units)


# ---------- local search ----------

def _improve(tables: list[Table], rng: random.Random) -> None:
    """Swap two single people with the same role between tables if it helps."""
    if len(tables) < 2:
        return
    for _ in range(SWAP_ITERATIONS):
        t1, t2 = rng.sample(tables, 2)
        singles1 = [u for u in t1.units if u.size == 1]
        singles2 = [u for u in t2.units if u.size == 1]
        if not singles1 or not singles2:
            continue
        u1, u2 = rng.choice(singles1), rng.choice(singles2)
        if u1.people[0]["role"] != u2.people[0]["role"]:
            continue  # same role keeps both tables balanced
        new1 = [u2 if u is u1 else u for u in t1.units]
        new2 = [u1 if u is u2 else u for u in t2.units]
        p1 = [p for u in new1 for p in u.people]
        p2 = [p for u in new2 for p in u.people]
        if not (compatible(p1) and compatible(p2)):
            continue
        if score(p1) + score(p2) > score(t1.people) + score(t2.people):
            t1.units, t2.units = new1, new2


# ---------- public entry point ----------

def match(profiles: list[dict], seed: int | None = None, priority: set[str] | None = None) -> dict:
    """profiles: dicts with email, lunch_id, role, mensa, faculty, languages (list),
    slots (list), answers (dict), age, age_min, age_max (None = no limit),
    friend_email (optional).

    priority: emails of people waitlisted last round; they are seated first.

    Returns {"tables": [...], "waitlist": [...], "stats": {...}}.
    """
    rng = random.Random(seed)
    priority = priority or set()
    units = build_units(profiles)

    tables: list[Table] = []
    waitlist: list[Unit] = []
    for mensa in sorted({u.mensa for u in units}):
        cu = [u for u in units if u.mensa == mensa]
        t, left = _build_tables(cu, rng, priority)
        _improve(t, rng)
        tables += t
        waitlist += left

    result_tables = []
    for i, t in enumerate(sorted(tables, key=lambda t: (t.people[0]["mensa"], options.SLOTS.index(pick_slot(t.people)))), start=1):
        people = t.people
        result_tables.append({
            "table_no": i,
            "mensa": people[0]["mensa"],
            "slot": pick_slot(people),
            "people": people,
            "languages": sorted(common(people, "languages")),
            "shared": shared_picks(people),
            "score": round(score(people), 1),
        })

    waiting = [p for u in waitlist for p in u.people]
    seated = sum(len(t["people"]) for t in result_tables)
    stats = {
        "registered": len(profiles),
        "newcomers": sum(p["role"] == "newcomer" for p in profiles),
        "locals": sum(p["role"] == "local" for p in profiles),
        "tables": len(result_tables),
        "seated": seated,
        "waitlist": len(waiting),
        "ideal_tables": sum(
            1 for t in result_tables
            if len(t["people"]) == 4 and sum(p["role"] == "newcomer" for p in t["people"]) == 2
        ),
    }
    return {"tables": result_tables, "waitlist": waiting, "stats": stats}


def waitlist_reason(person: dict, profiles: list[dict]) -> str:
    """Plain-language reason someone couldn't be seated (for the admin page)."""
    other_role = "local" if person["role"] == "newcomer" else "newcomer"
    same_mensa = [p for p in profiles if p["mensa"] == person["mensa"] and p["email"] != person["email"]]
    counterpart = [p for p in same_mensa if p["role"] == other_role]
    if not counterpart:
        return f"No {other_role}s registered at this Mensa yet"
    slot_ok = [p for p in counterpart if set(p["slots"]) & set(person["slots"])]
    if not slot_ok:
        return f"No {other_role} shares a lunch time"
    lang_ok = [p for p in slot_ok if set(p["languages"]) & set(person["languages"])]
    if not lang_ok:
        return f"No {other_role} at a shared time speaks a shared language"
    age_fit = [p for p in lang_ok if age_ok(person, p)]
    if not age_fit:
        return f"No {other_role} at a shared time fits the age preferences"
    return f"Not enough {other_role}s at shared times this round"
