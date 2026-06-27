from fastapi import FastAPI, Request, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
import aiosqlite
import json
from datetime import date, timedelta

from routes.ai_routes import router
from routes.scanner_routes import router as scanner_router
from database.db_config import init_db, DB_PATH
from database.auth import get_user_id, get_username, require_login
from database.avatars import AVATARS
from database.template_context import build_template_context, fetch_user
from config.settings import SECRET_KEY
from config.templates import templates

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)


async def template_context(request: Request, **extra):
    return await build_template_context(request, **extra)


@app.on_event("startup")
async def startup_event():
    await init_db()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA synchronous=NORMAL")
        await db.execute("PRAGMA cache_size=-32000")
        await db.execute("PRAGMA temp_store=MEMORY")
        await db.commit()


app.mount("/static", StaticFiles(directory="static"), name="static")
app.include_router(router)
app.include_router(scanner_router)


CURRENCY_SYMBOLS = {
    "USD": "$", "EUR": "€", "GBP": "£", "GEL": "₾", "TRY": "₺",
    "JPY": "¥", "KRW": "₩", "INR": "₹", "AUD": "A$", "CAD": "C$",
    "CHF": "CHF ", "ZAR": "R", "SEK": "kr ",
}


@app.get("/")
async def read_root(request: Request):
    user_id = get_user_id(request)
    subscriptions = []
    if user_id is not None:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY renewal_date ASC, id DESC",
                (user_id,),
            )
            subscriptions = await cursor.fetchall()

    subs_for_js = []
    today = date.today()
    renewal_reminders = []
    cut_candidates = []
    monthly_by_currency: dict[str, float] = {}
    # Track most expensive per currency — never compare across currencies
    most_expensive_by_currency: dict[str, dict] = {}

    for s in subscriptions:
        currency = s["currency"] if s["currency"] else "USD"
        cost = s["cost"]
        cycle = s["cycle"]

        subs_for_js.append({
            "name": s["name"],
            "cost": cost,
            "currency": currency,
            "cycle": cycle,
            "category": s["category"] if s["category"] else "Other",
        })

        # Monthly-equivalent per currency bucket
        mo_cost = cost if cycle == "Monthly" else cost / 12
        monthly_by_currency[currency] = monthly_by_currency.get(currency, 0.0) + mo_cost

        # Most expensive: only compare within the same currency
        current_best = most_expensive_by_currency.get(currency)
        if current_best is None or cost > current_best["cost"]:
            most_expensive_by_currency[currency] = {
                "name": s["name"],
                "cost": cost,
                "cycle": cycle,
            }

        # Renewal reminders: 1–7 days out
        if s["renewal_date"]:
            try:
                rdate = date.fromisoformat(s["renewal_date"])
                days_left = (rdate - today).days
                if 1 <= days_left <= 7:
                    renewal_reminders.append({
                        "name": s["name"],
                        "renewal_date": s["renewal_date"],
                        "days_left": days_left,
                        "cost": cost,
                        "currency": currency,
                        "cycle": cycle,
                    })
            except (ValueError, TypeError):
                pass

        # Cut-this candidates: added 60+ days ago, not recently renewed
        if s["first_detected"]:
            try:
                fdate = date.fromisoformat(s["first_detected"])
                age_days = (today - fdate).days
                if age_days >= 60:
                    is_stale = True
                    if s["renewal_date"]:
                        try:
                            if (date.fromisoformat(s["renewal_date"]) - today).days <= 14:
                                is_stale = False
                        except (ValueError, TypeError):
                            pass
                    if is_stale:
                        cut_candidates.append({
                            "name": s["name"],
                            "cost": cost,
                            "currency": currency,
                            "cycle": cycle,
                            "age_days": age_days,
                            "id": s["id"],
                        })
            except (ValueError, TypeError):
                pass

    # currency_totals carries everything the template needs per currency.
    # most_expensive is embedded here so the template never needs to do
    # a cross-currency comparison itself.
    currency_totals = []
    for cur, mo in sorted(monthly_by_currency.items()):
        currency_totals.append({
            "currency": cur,
            "symbol": CURRENCY_SYMBOLS.get(cur, f"{cur} "),
            "monthly": round(mo, 2),
            "annual": round(mo * 12, 2),
            "most_expensive": most_expensive_by_currency.get(cur),  # same currency only
        })

    ctx = await template_context(request, subscriptions=subscriptions)
    ctx["subscriptions_json"] = json.dumps(subs_for_js)
    ctx["today"] = today.isoformat()
    ctx["renewal_reminders"] = renewal_reminders
    ctx["cut_candidates"] = cut_candidates
    ctx["currency_totals"] = currency_totals
    # most_expensive removed — it's now inside each currency_totals entry
    return templates.TemplateResponse(request=request, name="home.html", context=ctx)


@app.post("/add-subscription")
async def handle_add_subscription(
    request: Request,
    name: str = Form(...),
    cost: float = Form(...),
    cycle: str = Form(...),
    method: str = Form(...),
    renewal_date: str = Form(...),
    currency: str = Form("USD"),
    category: str = Form("Other"),
):
    redirect = require_login(request)
    if redirect:
        return redirect

    if cycle not in ("Monthly", "Yearly"):
        return RedirectResponse(url="/", status_code=303)

    user_id = get_user_id(request)
    today = date.today().isoformat()

    valid_categories = ["Streaming", "Music", "Gaming", "Productivity", "AI Tools",
                        "Design", "Security", "Cloud", "Learning", "Social", "Other"]
    if category not in valid_categories:
        category = "Other"

    if not currency or len(currency) != 3:
        currency = "USD"
    currency = currency.upper()

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        cursor = await db.execute(
            """INSERT INTO subscriptions
               (name, cost, currency, cycle, method, renewal_date, category, user_id, first_detected)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (name.strip(), cost, currency, cycle, method.strip(), renewal_date, category, user_id, today),
        )
        sub_id = cursor.lastrowid
        await db.execute(
            """INSERT INTO subscription_history
               (subscription_id, user_id, name, cost, cycle, renewal_date, recorded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (sub_id, user_id, name.strip(), cost, cycle, renewal_date, today),
        )
        await db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/delete-subscription/{sub_id}")
async def handle_delete_subscription(request: Request, sub_id: int):
    redirect = require_login(request)
    if redirect:
        return redirect

    user_id = get_user_id(request)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute(
            "DELETE FROM subscriptions WHERE id = ? AND user_id = ?",
            (sub_id, user_id),
        )
        await db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.get("/introduction")
async def introduction_page(request: Request):
    return templates.TemplateResponse(
        request, name="Introduction.html", context=await template_context(request)
    )


@app.get("/login")
async def login_page(request: Request):
    if get_user_id(request) is not None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request, name="Login.html",
        context=await template_context(request, error=None),
    )


@app.post("/login")
async def handle_login(
    request: Request, username: str = Form(...), password: str = Form(...)
):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password),
        )
        user = await cursor.fetchone()

    if user:
        request.session["user_id"] = user["id"]
        request.session["username"] = user["username"]
        return RedirectResponse(url="/", status_code=303)

    return templates.TemplateResponse(
        request, name="Login.html",
        context=await template_context(request, error="Invalid username or password."),
    )


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/profile")
async def profile_page(request: Request, msg: str = None):
    redirect = require_login(request)
    if redirect:
        return redirect

    user_id = get_user_id(request)
    user = await fetch_user(user_id)
    success = None
    if msg == "avatar_updated":
        success = "Profile picture updated!"
    elif msg == "password_updated":
        success = "Password updated successfully!"

    return templates.TemplateResponse(
        request, name="profile.html",
        context=await template_context(request, user=user, success=success, error=None),
    )


@app.post("/profile/avatar")
async def update_avatar(request: Request, avatar: str = Form(...)):
    redirect = require_login(request)
    if redirect:
        return redirect

    if avatar not in AVATARS:
        return RedirectResponse(url="/profile", status_code=303)

    user_id = get_user_id(request)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("UPDATE users SET avatar = ? WHERE id = ?", (avatar, user_id))
        await db.commit()
    return RedirectResponse(url="/profile?msg=avatar_updated", status_code=303)


@app.post("/profile/password")
async def update_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
):
    redirect = require_login(request)
    if redirect:
        return redirect

    user_id = get_user_id(request)
    if len(new_password) < 6:
        return templates.TemplateResponse(
            request, name="profile.html",
            context=await template_context(
                request, user=await fetch_user(user_id), success=None,
                error="New password must be at least 6 characters.",
            ),
        )

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT password FROM users WHERE id = ?", (user_id,))
        user = await cursor.fetchone()
        if not user or user["password"] != current_password:
            return templates.TemplateResponse(
                request, name="profile.html",
                context=await template_context(
                    request, user=await fetch_user(user_id), success=None,
                    error="Current password is incorrect.",
                ),
            )
        await db.execute("UPDATE users SET password = ? WHERE id = ?", (new_password, user_id))
        await db.commit()

    return RedirectResponse(url="/profile?msg=password_updated", status_code=303)


@app.get("/signup")
async def signup_page(request: Request):
    if get_user_id(request) is not None:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request, name="Sign_up.html",
        context=await template_context(request, error=None, success=None),
    )


@app.post("/signup")
async def handle_signup(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
):
    username = username.strip()
    if len(username) < 2:
        return templates.TemplateResponse(
            request, name="Sign_up.html",
            context=await template_context(
                request, error="Username must be at least 2 characters.", success=None
            ),
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            request, name="Sign_up.html",
            context=await template_context(
                request, error="Password must be at least 6 characters.", success=None
            ),
        )

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        try:
            await db.execute(
                "INSERT INTO users (username, password) VALUES (?, ?)",
                (username, password),
            )
            await db.commit()
            return templates.TemplateResponse(
                request, name="Sign_up.html",
                context=await template_context(
                    request, success="Account created! You can now log in.", error=None,
                ),
            )
        except aiosqlite.IntegrityError:
            return templates.TemplateResponse(
                request, name="Sign_up.html",
                context=await template_context(
                    request, error="Username already taken.", success=None,
                ),
            )


@app.get("/privacy")
async def privacy_page(request: Request):
    return templates.TemplateResponse(
        request, name="Privacy_policy.html", context=await template_context(request)
    )
