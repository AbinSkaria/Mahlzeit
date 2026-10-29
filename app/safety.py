"""Reporting a tablemate without giving up anonymity.

How anonymity is kept:
  - Students pick the person by the animal they had at the table ("the Fox"),
    which is linked to their Lunch ID; nobody needs a name. If they're not sure
    who it was, they can report the table as a whole.
  - The reported person is never told who reported them, or that anyone did.
  - The team sees Lunch IDs only. An email is revealed only by an explicit
    "reveal" action, which is logged (who, when). The reporter's email can only
    be revealed if they ticked "you may contact me".

What happens automatically, without anyone reading the report:
  - The two people are never seated at the same table again.
  - Someone reported by 2 or more different people is paused from matching
    until the team has looked at the reports.
"""
from .db import connect

CATEGORIES = {
    "uncomfortable": "Made me feel uncomfortable",
    "disrespect": "Disrespectful or offensive comments",
    "discrimination": "Discrimination (origin, religion, gender, …)",
    "harassment": "Harassment or unwanted contact",
    "no_show": "Didn't show up / unreliable",
    "other": "Something else",
}
PAUSE_AFTER_REPORTERS = 2


def create_report(table_id: int | None, reporter_id: int, reported_id: int | None,
                  category: str, details: str | None, contact_ok: bool) -> None:
    with connect() as conn:
        conn.execute(
            """INSERT INTO reports (table_id, reporter_id, reported_id, category, details, contact_ok)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (table_id, reporter_id, reported_id, category, details, int(contact_ok)),
        )


def reported_by_me(reporter_id: int) -> set[int]:
    with connect() as conn:
        return {r[0] for r in conn.execute(
            "SELECT reported_id FROM reports WHERE reporter_id = ?", (reporter_id,))}


def avoid_pairs() -> dict[int, set[int]]:
    """user_id -> user_ids they must never share a table with (both directions)."""
    out: dict[int, set[int]] = {}
    with connect() as conn:
        for a, b in conn.execute("SELECT reporter_id, reported_id FROM reports WHERE reported_id IS NOT NULL"):
            out.setdefault(a, set()).add(b)
            out.setdefault(b, set()).add(a)
    return out


def paused_users() -> dict[int, int]:
    """user_id -> number of different people with an open report about them,
    for everyone at or above the pause threshold."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT reported_id, COUNT(DISTINCT reporter_id) AS n FROM reports
               WHERE status = 'open' AND reported_id IS NOT NULL
               GROUP BY reported_id HAVING n >= ?""",
            (PAUSE_AFTER_REPORTERS,),
        ).fetchall()
    return {r["reported_id"]: r["n"] for r in rows}


def list_reports() -> list[dict]:
    """For the admin page. Emails are only included if a reveal was logged."""
    with connect() as conn:
        rows = conn.execute(
            """SELECT r.*, rep.lunch_id AS reporter_lid, red.lunch_id AS reported_lid,
                      rep.email AS reporter_email, red.email AS reported_email,
                      t.table_no, t.mensa, t.slot,
                      (SELECT animal FROM match_seats s WHERE s.table_id = r.table_id AND s.user_id = r.reporter_id) AS reporter_animal,
                      (SELECT animal FROM match_seats s WHERE s.table_id = r.table_id AND s.user_id = r.reported_id) AS reported_animal,
                      (SELECT COUNT(*) FROM reveal_log l WHERE l.report_id = r.id) AS reveals,
                      (SELECT GROUP_CONCAT(admin_email || ' at ' || created_at, '; ')
                         FROM reveal_log l WHERE l.report_id = r.id) AS reveal_info
               FROM reports r
               JOIN users rep ON rep.id = r.reporter_id
               LEFT JOIN users red ON red.id = r.reported_id
               LEFT JOIN match_tables t ON t.id = r.table_id
               ORDER BY r.status = 'resolved', r.id DESC"""
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["category_label"] = CATEGORIES.get(d["category"], d["category"])
        if not d["reveals"]:
            d["reported_email"] = None
            d["reporter_email"] = None
        elif not d["contact_ok"]:
            d["reporter_email"] = None  # never revealed without the reporter's OK
        out.append(d)
    return out


def reveal(report_id: int, admin_email: str) -> None:
    with connect() as conn:
        conn.execute("INSERT INTO reveal_log (report_id, admin_email) VALUES (?, ?)", (report_id, admin_email))


def resolve(report_id: int) -> None:
    """Closes the report (lifts a pause if no open reports remain). The two people
    still won't be seated together again."""
    with connect() as conn:
        conn.execute("UPDATE reports SET status = 'resolved', resolved_at = datetime('now') WHERE id = ?",
                     (report_id,))
