"""Mahlzeit: lunch matching for THWS Fit4Germany.

Run:  uvicorn app.main:app --reload
"""
import logging
import os
import secrets
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from . import auth, mailer, options, profiles, rounds, safety
from .db import init_db

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("mahlzeit")

BASE_DIR = Path(__file__).parent
# Shows the magic link on screen when no SMTP server is configured.
# Turn this OFF in production.
DEMO_MODE = os.environ.get("MAHLZEIT_DEMO", "1") == "1"

SECRET_KEY = os.environ.get("MAHLZEIT_SECRET")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)
    log.warning("MAHLZEIT_SECRET not set: using a random key (everyone is logged out on restart).")

app = FastAPI(title="Mahlzeit", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="mahlzeit_session",
    max_age=60 * 60 * 24 * 30,  # 30 days, so students don't re-login every week
    same_site="lax",
    https_only=os.environ.get("MAHLZEIT_HTTPS", "0") == "1",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")
templates.env.globals["opt"] = options  # form choices available in every template
templates.env.globals["slot_label"] = rounds.slot_label
templates.env.globals["age_label"] = options.age_label
templates.env.globals["age_range_label"] = options.age_range_label
templates.env.globals["animal"] = lambda key: options.ANIMAL.get(key or "", ("🍽️", "Guest"))
templates.env.globals["mensa_name"] = lambda mid: options.MENSA_NAME.get(mid, mid)

# Who may open /admin. Comma-separated emails. If empty in demo mode,
# every logged-in user is treated as admin so the demo just works.
ADMINS = {e.strip().lower() for e in os.environ.get("MAHLZEIT_ADMINS", "").split(",") if e.strip()}


def is_admin(user: dict | None) -> bool:
    if not user:
        return False
    return user["email"] in ADMINS if ADMINS else DEMO_MODE


templates.env.globals["is_admin"] = is_admin


@app.on_event("startup")
def _startup() -> None:
    init_db()


def current_user(request: Request) -> dict | None:
    uid = request.session.get("user_id")
    return auth.get_user(uid) if uid else None


# ---------- Start page ----------

@app.get("/", response_class=HTMLResponse)
def start(request: Request):
    return templates.TemplateResponse(
        request, "index.html",
        {"user": current_user(request), "deleted": request.query_params.get("deleted") == "1"},
    )


# ---------- Login (magic link) ----------

@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if current_user(request):
        return RedirectResponse("/home", status_code=303)
    return templates.TemplateResponse(request, "login.html", {"error": None, "email": ""})


@app.post("/login", response_class=HTMLResponse)
def login_submit(request: Request, email: str = Form(...)):
    email = auth.normalize_email(email)
    error = auth.validate_email(email)
    if error:
        return templates.TemplateResponse(
            request, "login.html", {"error": error, "email": email}, status_code=400
        )
    if auth.recently_requested(email):
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "We just sent you a link. Check your inbox (and spam) or try again in 30 seconds.",
             "email": email},
            status_code=429,
        )

    token = auth.create_login_token(email)
    link = str(request.url_for("verify")) + f"?token={token}"
    try:
        mailer.send_login_link(email, link)
    except Exception:
        # e.g. wrong SMTP password: log the details, show the student a friendly message
        log.exception("Sending login email to %s failed", email)
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "We couldn't send the email right now. Please try again in a minute.",
             "email": email},
            status_code=502,
        )

    demo_link = link if (DEMO_MODE and not mailer.smtp_configured()) else None
    return templates.TemplateResponse(
        request, "check_email.html", {"email": email, "demo_link": demo_link}
    )


@app.get("/auth/verify", name="verify")
def verify(request: Request, token: str = ""):
    user = auth.consume_login_token(token) if token else None
    if user is None:
        return templates.TemplateResponse(
            request, "login.html",
            {"error": "That link has expired or was already used. Enter your email for a new one.",
             "email": ""},
            status_code=400,
        )
    request.session.clear()
    request.session["user_id"] = user["id"]
    return RedirectResponse("/home", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# ---------- Logged-in area ----------

@app.get("/home", response_class=HTMLResponse)
def home(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    profile = profiles.get_profile(user["id"])
    complete = bool(profile and profile["completed"])
    rnd = rounds.latest_round() if complete else None
    table = None
    if rnd:
        table = next((t for t in rnd["tables"] if any(p["user_id"] == user["id"] for p in t["people"])), None)
    return templates.TemplateResponse(
        request, "home.html",
        {"user": user, "profile": profile if complete else None, "started": profile is not None,
         "next_step": profiles.first_open_step(profile),
         "saved": request.query_params.get("saved") == "1",
         "thanks": request.query_params.get("thanks") == "1",
         "reported": request.query_params.get("reported") == "1",
         "checkin": request.query_params.get("checkin"),
         "checkin_closed": rounds.checkin_window(table["slot"]) if table else None,
         "table": table, "round_exists": rnd is not None,
         "my_feedback": table["feedback"].get(user["id"]) if table else None},
    )


# ---------- Lunch profile: three pages ----------

STEP_INFO = {
    "about": ("About you", "profile_about.html"),
    "where": ("Where & when", "profile_where.html"),
    "prefs": ("Who you'd like to meet", "profile_prefs.html"),
}


def _render_step(request, user, step, p, errors, status=200):
    return templates.TemplateResponse(
        request, STEP_INFO[step][1],
        {"user": user, "p": p, "errors": errors, "step": step,
         "step_no": profiles.STEP_ORDER.index(step) + 1, "steps": STEP_INFO,
         "is_new": not p.get("completed")},
        status_code=status,
    )


@app.get("/profile")
def profile_start(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    p = profiles.get_profile(user["id"])
    step = "about" if p and p["completed"] else profiles.first_open_step(p)
    return RedirectResponse(f"/profile/{step}", status_code=303)


@app.get("/profile/{step}", response_class=HTMLResponse)
def profile_step(request: Request, step: str):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if step not in STEP_INFO:
        return RedirectResponse("/profile", status_code=303)
    p = profiles.get_profile(user["id"]) or {}
    # Pages are filled in order; jumping ahead goes back to the first open page.
    for prev in profiles.STEP_ORDER[:profiles.STEP_ORDER.index(step)]:
        if not profiles.step_done(p, prev):
            return RedirectResponse(f"/profile/{prev}", status_code=303)
    return _render_step(request, user, step, p, {})


@app.post("/profile/{step}", response_class=HTMLResponse)
async def profile_step_submit(request: Request, step: str):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    if step not in STEP_INFO:
        return RedirectResponse("/profile", status_code=303)
    form = await request.form()
    if step == "about":
        data, errors = profiles.parse_about(form)
    elif step == "where":
        data, errors = profiles.parse_where(form)
    else:
        data, errors = profiles.parse_prefs(form, user["email"])
    if errors:
        # Re-show the page with what they entered, plus messages next to each problem.
        p = {**(profiles.get_profile(user["id"]) or {}), **data,
             "consent_checked": form.get("consent") == "yes"}
        return _render_step(request, user, step, p, errors, status=400)
    profiles.save_step(user["id"], step, data)
    idx = profiles.STEP_ORDER.index(step)
    if idx + 1 < len(profiles.STEP_ORDER):
        return RedirectResponse(f"/profile/{profiles.STEP_ORDER[idx + 1]}", status_code=303)
    return RedirectResponse("/home?saved=1", status_code=303)


# ---------- Feedback after the lunch (optional, last page) ----------

def _my_table(user_id: int):
    rnd = rounds.latest_round()
    if not rnd:
        return None
    return next((t for t in rnd["tables"] if any(p["user_id"] == user_id for p in t["people"])), None)


@app.get("/feedback", response_class=HTMLResponse)
def feedback_form(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    table = _my_table(user["id"])
    if not table:
        return RedirectResponse("/home", status_code=303)
    return templates.TemplateResponse(
        request, "feedback.html",
        {"user": user, "table": table, "f": table["feedback"].get(user["id"]) or {}},
    )


@app.post("/feedback")
async def feedback_submit(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    table = _my_table(user["id"])
    if not table:
        return RedirectResponse("/home", status_code=303)
    rounds.save_feedback(table["id"], user["id"], rounds.parse_feedback(await request.form()))
    return RedirectResponse("/home?thanks=1", status_code=303)


@app.post("/checkin")
async def checkin(request: Request):
    """The student types the 4-digit code from the table card at the Mensa."""
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    table = _my_table(user["id"])
    if not table:
        return RedirectResponse("/home", status_code=303)
    result = rounds.check_in(table, user["id"], (await request.form()).get("code", ""))
    if result == "ok":
        return RedirectResponse("/badge", status_code=303)
    return RedirectResponse(f"/home?checkin={result}#checkin", status_code=303)


@app.get("/badge", response_class=HTMLResponse)
def badge(request: Request):
    """Full-screen 'code accepted' page with your animal, to show the table."""
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    table = _my_table(user["id"])
    me = next((p for p in table["people"] if p["user_id"] == user["id"]), None) if table else None
    if not me or not me.get("checked_in_at"):
        return RedirectResponse("/home", status_code=303)
    return templates.TemplateResponse(request, "badge.html", {"user": user, "table": table, "me": me})


@app.post("/lunch/done")
async def lunch_done(request: Request):
    """'I'm done with lunch' or 'I couldn't make it' -> records attendance, then the feedback page."""
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    table = _my_table(user["id"])
    if not table:
        return RedirectResponse("/home", status_code=303)
    attended = (await request.form()).get("attended")
    if attended in ("yes", "no"):
        rounds.mark_attended(table["id"], user["id"], attended)
    return RedirectResponse("/feedback", status_code=303)


# ---------- Report a tablemate (anonymous to them) ----------

@app.get("/report", response_class=HTMLResponse)
def report_form(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    table = _my_table(user["id"])
    if not table:
        return RedirectResponse("/home", status_code=303)
    return templates.TemplateResponse(
        request, "report.html",
        {"user": user, "table": table, "categories": safety.CATEGORIES, "errors": {}, "f": {},
         "already": safety.reported_by_me(user["id"])},
    )


@app.post("/report", response_class=HTMLResponse)
async def report_submit(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse("/login", status_code=303)
    table = _my_table(user["id"])
    if not table:
        return RedirectResponse("/home", status_code=303)
    form = await request.form()
    mates = {str(p["user_id"]): p for p in table["people"] if p["user_id"] != user["id"]}
    errors = {}
    who = form.get("who")
    if who not in mates and who != "unsure":
        errors["who"] = "Pick the person, or \"I'm not sure who\"."
    category = form.get("category")
    if category not in safety.CATEGORIES:
        errors["category"] = "Pick what happened."
    details = (form.get("details") or "").strip()[:1000] or None
    if errors:
        return templates.TemplateResponse(
            request, "report.html",
            {"user": user, "table": table, "categories": safety.CATEGORIES, "errors": errors,
             "f": dict(form), "already": safety.reported_by_me(user["id"])},
            status_code=400,
        )
    reported_id = mates[who]["user_id"] if who in mates else None
    safety.create_report(table["id"], user["id"], reported_id, category, details,
                         form.get("contact_ok") == "yes")
    return RedirectResponse("/home?reported=1", status_code=303)


@app.post("/account/delete")
def account_delete(request: Request):
    user = current_user(request)
    if user:
        profiles.delete_account(user["id"], user["email"])
    request.session.clear()
    return RedirectResponse("/?deleted=1", status_code=303)


# ---------- Admin (Fit4Germany team) ----------

@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    user = current_user(request)
    if not is_admin(user):
        return RedirectResponse("/login" if not user else "/home", status_code=303)
    all_profiles = rounds.load_profiles()
    stats = {
        "registered": len(all_profiles),
        "newcomers": sum(p["role"] == "newcomer" for p in all_profiles),
        "locals": sum(p["role"] == "local" for p in all_profiles),
        "by_mensa": [
            (options.MENSA_NAME[mid],
             sum(p["mensa"] == mid and p["role"] == "newcomer" for p in all_profiles),
             sum(p["mensa"] == mid and p["role"] == "local" for p in all_profiles))
            for mid in options.MENSA_NAME
        ],
    }
    return templates.TemplateResponse(
        request, "admin.html",
        {"user": user, "stats": stats, "rnd": rounds.latest_round(), "demo_admin": not ADMINS,
         "reports": safety.list_reports(), "paused": safety.paused_users(),
         "categories": safety.CATEGORIES},
    )


@app.get("/admin/cards", response_class=HTMLResponse)
def admin_cards(request: Request):
    """Printable table cards (number, Mensa, time, check-in code) to put on the tables."""
    user = current_user(request)
    if not is_admin(user):
        return RedirectResponse("/home", status_code=303)
    return templates.TemplateResponse(request, "cards.html", {"user": user, "rnd": rounds.latest_round()})


@app.post("/admin/reports/{report_id}/{action}")
def admin_report_action(request: Request, report_id: int, action: str):
    user = current_user(request)
    if not is_admin(user):
        return RedirectResponse("/home", status_code=303)
    if action == "reveal":
        safety.reveal(report_id, user["email"])
    elif action == "resolve":
        safety.resolve(report_id)
    return RedirectResponse(f"/admin#report-{report_id}", status_code=303)


@app.post("/admin/match")
def admin_match(request: Request):
    if not is_admin(current_user(request)):
        return RedirectResponse("/home", status_code=303)
    rounds.run_round()
    return RedirectResponse("/admin#results", status_code=303)


@app.get("/privacy", response_class=HTMLResponse)
def privacy(request: Request):
    return templates.TemplateResponse(request, "privacy.html", {"user": current_user(request)})
