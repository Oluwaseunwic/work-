"""
Job Recruitment Website - Flask backend
Built by WIC Technologies  |  "Where Wisdom Builds Innovation"

Run:  python app.py
Site:  http://127.0.0.1:5000
Admin: http://127.0.0.1:5000/admin
"""
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, date
from functools import wraps

from flask import (
    Flask, abort, flash, g, redirect, render_template, request,
    send_from_directory, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
INSTANCE_DIR = os.path.join(BASE_DIR, "instance")
CV_DIR = os.path.join(INSTANCE_DIR, "cv_uploads")      # private - only admin can download
LOGO_DIR = os.path.join(BASE_DIR, "static", "uploads")  # public - site logo
DB_PATH = os.path.join(INSTANCE_DIR, "site.db")

for _d in (INSTANCE_DIR, CV_DIR, LOGO_DIR):
    os.makedirs(_d, exist_ok=True)

app = Flask(__name__, instance_path=INSTANCE_DIR)
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024  # 6 MB per request


def _load_secret_key():
    env_key = os.environ.get("SECRET_KEY")
    if env_key:
        return env_key
    key_file = os.path.join(INSTANCE_DIR, "secret.key")
    if not os.path.exists(key_file):
        with open(key_file, "w") as fh:
            fh.write(secrets.token_hex(32))
    with open(key_file) as fh:
        return fh.read().strip()


app.secret_key = _load_secret_key()
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("HTTPS", "0") == "1",
    PERMANENT_SESSION_LIFETIME=60 * 60 * 8,
)

ALLOWED_CV = {"pdf", "doc", "docx"}
ALLOWED_LOGO = {"png", "jpg", "jpeg", "webp", "svg"}

CATEGORIES = [
    "Information Technology", "Engineering", "Finance & Accounting",
    "Sales & Marketing", "Healthcare", "Education", "Logistics & Supply Chain",
    "Administration", "Hospitality", "Legal", "Customer Service", "Other",
]
JOB_TYPES = ["Full-time", "Part-time", "Contract", "Internship", "Remote"]
APP_STATUSES = ["new", "reviewed", "shortlisted", "rejected"]

DEFAULT_SETTINGS = {
    "site_name": "TalentBridge",
    "tagline": "Connecting skilled people with the right opportunities",
    "email": "info@yourcompany.com",
    "phone": "+1 000 000 0000",
    "whatsapp": "+1 000 000 0000",
    "address": "Your office address, City, USA",
    "hours": "Mon - Fri, 8:00am - 5:00pm",
    "facebook": "",
    "instagram": "",
    "linkedin": "",
    "logo": "",
}


# --------------------------------------------------------------------------- #
#  Database helpers
# --------------------------------------------------------------------------- #
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL DEFAULT ''
);
CREATE TABLE IF NOT EXISTS admins (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    company      TEXT NOT NULL,
    location     TEXT NOT NULL,
    category     TEXT NOT NULL,
    job_type     TEXT NOT NULL,
    salary       TEXT DEFAULT '',
    description  TEXT NOT NULL,
    requirements TEXT DEFAULT '',
    deadline     TEXT DEFAULT '',
    featured     INTEGER NOT NULL DEFAULT 0,
    status       TEXT NOT NULL DEFAULT 'open',
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS applications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id       INTEGER REFERENCES jobs(id) ON DELETE SET NULL,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL,
    phone        TEXT NOT NULL,
    cover_letter TEXT DEFAULT '',
    cv_filename  TEXT NOT NULL,
    cv_original  TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'new',
    created_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS employer_requests (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    company        TEXT NOT NULL,
    contact_person TEXT NOT NULL,
    email          TEXT NOT NULL,
    phone          TEXT NOT NULL,
    message        TEXT NOT NULL,
    status         TEXT NOT NULL DEFAULT 'new',
    created_at     TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    email      TEXT NOT NULL,
    subject    TEXT NOT NULL,
    message    TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_apps_job      ON applications(job_id);
"""

DEMO_JOBS = [
    ("Frontend Developer", "Bluepeak Digital", "New York, NY", "Information Technology", "Full-time",
     "$900 - $1,300 / month",
     "We are looking for a Frontend Developer to build fast, accessible interfaces for our growing client base. "
     "You will work closely with designers and backend engineers to ship features every week.\n\n"
     "What you will do:\n- Build responsive pages with HTML, CSS and JavaScript\n- Turn Figma designs into clean, reusable components\n"
     "- Optimise performance and fix browser quirks\n- Review code and share knowledge with the team",
     "- 2+ years of professional experience\n- Strong HTML, CSS and JavaScript\n- Experience with Git\n- Good communication skills", 1),
    ("Accountant", "Kingsway Holdings", "Los Angeles, CA", "Finance & Accounting", "Full-time",
     "$650 - $900 / month",
     "A well-established holdings company is hiring an Accountant to manage day-to-day bookkeeping, reconciliations and monthly reporting.\n\n"
     "Responsibilities:\n- Prepare monthly management accounts\n- Reconcile bank and supplier statements\n- Support audits and tax filing",
     "- B.Sc. in Accounting or related field\n- ICAN / ACCA (in progress is acceptable)\n- Proficiency in Excel and accounting software", 1),
    ("Sales Executive", "Northgate Supplies", "Chicago, IL", "Sales & Marketing", "Full-time",
     "$400 + commission",
     "Join a fast-moving supply company as a Sales Executive. You will find new clients, maintain existing accounts and hit monthly targets.",
     "- 1+ year in B2B sales\n- Confident communicator\n- Own transportation is an advantage", 0),
    ("Logistics Coordinator", "Swiftline Freight", "New York, NY", "Logistics & Supply Chain", "Full-time",
     "$520 - $730 / month",
     "Coordinate inbound and outbound shipments, track deliveries and keep customers updated. You will be the calm voice when schedules change.",
     "- Experience in freight or dispatch\n- Organised and detail focused\n- Comfortable with spreadsheets and tracking tools", 1),
    ("Registered Nurse", "Goldcrest Clinic", "Houston, TX", "Healthcare", "Full-time",
     "$570 - $780 / month",
     "Goldcrest Clinic is expanding and needs compassionate registered nurses for day and night shifts.",
     "- Valid RN licence\n- 2+ years clinical experience\n- Ability to work shifts", 0),
    ("Customer Support Agent", "Orbit Telecom", "Remote", "Customer Service", "Remote",
     "$310 - $440 / month",
     "Help customers by chat, email and phone. Training is provided; a positive attitude and clear writing matter most.",
     "- Good written and spoken English\n- Own laptop and stable internet\n- Available for rotating shifts", 0),
    ("Graphic Designer", "Pixelhouse Studio", "New York, NY", "Sales & Marketing", "Contract",
     "$470 / month",
     "Create social media graphics, brochures and brand assets for local and international clients.",
     "- Portfolio required\n- Photoshop, Illustrator or Figma\n- Eye for typography and layout", 0),
    ("Secondary School Teacher (Mathematics)", "Crestview Academy", "Seattle, WA", "Education", "Full-time",
     "$390 - $520 / month",
     "Teach Mathematics to JSS and SSS students and take part in school activities.",
     "- B.Ed or B.Sc with PGDE\n- 2+ years teaching experience\n- Strong classroom management", 0),
]


SALARY_TO_USD = {
    "₦350,000 - ₦500,000 / month": "$900 - $1,300 / month",
    "₦250,000 - ₦350,000 / month": "$650 - $900 / month",
    "₦150,000 + commission": "$400 + commission",
    "₦200,000 - ₦280,000 / month": "$520 - $730 / month",
    "₦220,000 - ₦300,000 / month": "$570 - $780 / month",
    "₦120,000 - ₦170,000 / month": "$310 - $440 / month",
    "₦180,000 / month": "$470 / month",
    "₦150,000 - ₦200,000 / month": "$390 - $520 / month",
}


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(SCHEMA)
    for k, v in DEFAULT_SETTINGS.items():
        db.execute("INSERT OR IGNORE INTO settings(key, value) VALUES (?, ?)", (k, v))

    # first-run admin account
    if db.execute("SELECT COUNT(*) FROM admins").fetchone()[0] == 0:
        username = os.environ.get("ADMIN_USER", "admin")
        password = os.environ.get("ADMIN_PASS", "ChangeMe@2026")
        db.execute("INSERT INTO admins(username, password_hash) VALUES (?, ?)",
                   (username, generate_password_hash(password)))
        print(f"\n  First run: admin account created -> username: {username} | password: {password}")
        print("  Log in at /admin and change the password straight away.\n")

    # Update the site's previous Nigeria-specific demo defaults to U.S. placeholders.
    db.execute("UPDATE settings SET value='+1 000 000 0000' WHERE key IN ('phone','whatsapp') AND value='+234 000 000 0000'")
    db.execute("UPDATE settings SET value='Your office address, City, USA' WHERE key='address' AND value='Your office address, City, Nigeria'")
    demo_location_updates = {
        "Frontend Developer": "New York, NY",
        "Accountant": "Los Angeles, CA",
        "Sales Executive": "Chicago, IL",
        "Logistics Coordinator": "New York, NY",
        "Registered Nurse": "Houston, TX",
        "Graphic Designer": "New York, NY",
        "Secondary School Teacher (Mathematics)": "Seattle, WA",
    }
    for title, location in demo_location_updates.items():
        db.execute("UPDATE jobs SET location=? WHERE title=? AND company IN ('Bluepeak Digital','Kingsway Holdings','Northgate Supplies','Swiftline Freight','Goldcrest Clinic','Pixelhouse Studio','Crestview Academy') AND location IN ('Lagos','Abuja','Port Harcourt','Ibadan','Enugu')", (location, title))

    # switch demo salaries saved by an earlier run from naira to dollars
    for old, new in SALARY_TO_USD.items():
        db.execute("UPDATE jobs SET salary=? WHERE salary=?", (new, old))

    # demo jobs so the site is not empty on first launch (admin can delete them)
    seeded = db.execute("SELECT value FROM settings WHERE key='demo_seeded'").fetchone()
    if not seeded:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for i, j in enumerate(DEMO_JOBS):
            db.execute(
                """INSERT INTO jobs(title, company, location, category, job_type, salary, description,
                                    requirements, featured, status, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?, 'open', datetime(?, ?))""",
                (j[0], j[1], j[2], j[3], j[4], j[5], j[6], j[7], j[8], now, f"-{i} days"),
            )
        db.execute("INSERT INTO settings(key, value) VALUES ('demo_seeded', '1')")
    db.commit()
    db.close()


# --------------------------------------------------------------------------- #
#  Security helpers: CSRF, login, rate limiting
# --------------------------------------------------------------------------- #
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_hex(16)
    return session["_csrf"]


@app.before_request
def csrf_protect():
    if request.method == "POST":
        sent = request.form.get("_csrf", "")
        if not sent or not secrets.compare_digest(sent, session.get("_csrf", "")):
            abort(400, "Your session expired. Please go back, refresh the page and try again.")


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin_id"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


_attempts = {}  # ip -> (count, first_attempt_time)


def too_many_attempts(ip, limit=6, window=600):
    count, first = _attempts.get(ip, (0, time.time()))
    if time.time() - first > window:
        _attempts.pop(ip, None)
        return False
    return count >= limit


def record_failed(ip):
    count, first = _attempts.get(ip, (0, time.time()))
    _attempts[ip] = (count + 1, first)


def allowed(filename, exts):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in exts


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def clean(value, maxlen=2000):
    return (value or "").strip()[:maxlen]


# --------------------------------------------------------------------------- #
#  Template helpers
# --------------------------------------------------------------------------- #
def get_settings():
    rows = get_db().execute("SELECT key, value FROM settings").fetchall()
    data = dict(DEFAULT_SETTINGS)
    data.update({r["key"]: r["value"] for r in rows})
    return data


@app.context_processor
def inject_globals():
    s = get_settings()
    wa = re.sub(r"\D", "", s.get("whatsapp", ""))
    return {
        "site": s,
        "wa_number": wa,
        "csrf_token": csrf_token,
        "year": datetime.now().year,
        "categories": CATEGORIES,
        "job_types": JOB_TYPES,
        "app_statuses": APP_STATUSES,
    }


@app.template_filter("ago")
def ago_filter(value):
    try:
        dt = datetime.strptime(value[:19], "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        return value or ""
    secs = int((datetime.now() - dt).total_seconds())
    if secs < 60:
        return "Just now"
    if secs < 3600:
        return f"{secs // 60} min ago"
    if secs < 86400:
        return f"{secs // 3600} hr ago"
    days = secs // 86400
    if days == 1:
        return "Yesterday"
    if days < 30:
        return f"{days} days ago"
    return dt.strftime("%d %b %Y")


@app.template_filter("nicedate")
def nicedate_filter(value):
    try:
        return datetime.strptime(value[:10], "%Y-%m-%d").strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value or ""


@app.template_filter("lines")
def lines_filter(value):
    """Split text into non-empty trimmed lines (used for bullet lists)."""
    return [ln.strip(" -•\t") for ln in (value or "").splitlines() if ln.strip(" -•\t")]


@app.template_filter("blocks")
def blocks_filter(value):
    """Turn plain text into ('para', text) and ('list', [items]) blocks.
    Lines starting with '-' or a bullet become list items; everything else is a paragraph."""
    out, bullets, para = [], [], []

    def flush_para():
        if para:
            out.append(("para", " ".join(para)))
            para.clear()

    def flush_bullets():
        if bullets:
            out.append(("list", bullets[:]))
            bullets.clear()

    for raw in (value or "").splitlines():
        line = raw.strip()
        if not line:
            flush_para()
            flush_bullets()
        elif line[0] in "-•*":
            flush_para()
            bullets.append(line.lstrip("-•* ").strip())
        else:
            flush_bullets()
            para.append(line)
    flush_para()
    flush_bullets()
    return out


def is_expired(job):
    if job["status"] != "open":
        return True
    if job["deadline"]:
        try:
            return datetime.strptime(job["deadline"], "%Y-%m-%d").date() < date.today()
        except ValueError:
            return False
    return False


app.jinja_env.globals["is_expired"] = is_expired


# --------------------------------------------------------------------------- #
#  Public pages
# --------------------------------------------------------------------------- #
@app.route("/")
def index():
    db = get_db()
    featured = db.execute(
        "SELECT * FROM jobs WHERE status='open' ORDER BY featured DESC, id DESC LIMIT 6"
    ).fetchall()
    stats = {
        "jobs": db.execute("SELECT COUNT(*) FROM jobs WHERE status='open'").fetchone()[0],
        "companies": db.execute("SELECT COUNT(DISTINCT company) FROM jobs").fetchone()[0],
        "applicants": db.execute("SELECT COUNT(*) FROM applications").fetchone()[0],
    }
    cat_rows = db.execute(
        "SELECT category, COUNT(*) AS n FROM jobs WHERE status='open' GROUP BY category ORDER BY n DESC LIMIT 8"
    ).fetchall()
    return render_template("index.html", featured=featured, stats=stats, cat_rows=cat_rows)


@app.route("/jobs")
def jobs():
    db = get_db()
    q = clean(request.args.get("q"), 80)
    category = clean(request.args.get("category"), 60)
    location = clean(request.args.get("location"), 60)
    jtype = clean(request.args.get("type"), 30)
    page = max(int(request.args.get("page", 1) or 1), 1) if request.args.get("page", "1").isdigit() else 1
    per_page = 9

    where, params = ["status='open'"], []
    if q:
        where.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        params += [f"%{q}%"] * 3
    if category:
        where.append("category = ?")
        params.append(category)
    if location:
        where.append("location LIKE ?")
        params.append(f"%{location}%")
    if jtype:
        where.append("job_type = ?")
        params.append(jtype)
    clause = " AND ".join(where)

    total = db.execute(f"SELECT COUNT(*) FROM jobs WHERE {clause}", params).fetchone()[0]
    pages = max((total + per_page - 1) // per_page, 1)
    page = min(page, pages)
    rows = db.execute(
        f"SELECT * FROM jobs WHERE {clause} ORDER BY featured DESC, id DESC LIMIT ? OFFSET ?",
        params + [per_page, (page - 1) * per_page],
    ).fetchall()
    locations = [r[0] for r in db.execute(
        "SELECT DISTINCT location FROM jobs WHERE status='open' ORDER BY location")]
    args = {k: v for k, v in request.args.items() if k != "page" and v}
    return render_template("jobs.html", jobs=rows, total=total, page=page, pages=pages,
                           q=q, sel_category=category, sel_location=location, sel_type=jtype,
                           locations=locations, args=args)


@app.route("/jobs/<int:job_id>")
def job_detail(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        abort(404)
    similar = db.execute(
        "SELECT * FROM jobs WHERE status='open' AND id != ? AND (category=? OR location=?) ORDER BY id DESC LIMIT 3",
        (job_id, job["category"], job["location"])).fetchall()
    return render_template("job_detail.html", job=job, similar=similar)


def save_application(job_id):
    """Validate + store an application. Returns (ok, message)."""
    if request.form.get("website"):  # honeypot - bots fill hidden fields
        return True, "Thank you!"
    name = clean(request.form.get("name"), 120)
    email = clean(request.form.get("email"), 160)
    phone = clean(request.form.get("phone"), 40)
    letter = clean(request.form.get("cover_letter"), 4000)
    cv = request.files.get("cv")

    if len(name) < 2 or not EMAIL_RE.match(email) or len(re.sub(r"\D", "", phone)) < 7:
        return False, "Please fill in your name, a valid email and a valid phone number."
    if not cv or not cv.filename:
        return False, "Please attach your CV (PDF, DOC or DOCX)."
    if not allowed(cv.filename, ALLOWED_CV):
        return False, "Your CV must be a PDF, DOC or DOCX file."

    stored = f"{int(time.time())}_{secrets.token_hex(4)}_{secure_filename(cv.filename)}"
    cv.save(os.path.join(CV_DIR, stored))
    db = get_db()
    db.execute(
        """INSERT INTO applications(job_id, name, email, phone, cover_letter, cv_filename, cv_original, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (job_id, name, email, phone, letter, stored, secure_filename(cv.filename),
         datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
    db.commit()
    return True, "Your application has been received. We will get in touch if you are shortlisted."


@app.route("/jobs/<int:job_id>/apply", methods=["POST"])
def apply(job_id):
    job = get_db().execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job or is_expired(job):
        abort(404)
    ok, msg = save_application(job_id)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("job_detail", job_id=job_id) + "#apply")


@app.route("/submit-cv", methods=["GET", "POST"])
def submit_cv():
    if request.method == "POST":
        ok, msg = save_application(None)
        flash(msg, "success" if ok else "error")
        return redirect(url_for("submit_cv") + "#form")
    return render_template("submit_cv.html")


@app.route("/employers", methods=["GET", "POST"])
def employers():
    if request.method == "POST":
        if request.form.get("website"):
            flash("Thank you!", "success")
            return redirect(url_for("employers") + "#form")
        company = clean(request.form.get("company"), 140)
        person = clean(request.form.get("contact_person"), 120)
        email = clean(request.form.get("email"), 160)
        phone = clean(request.form.get("phone"), 40)
        message = clean(request.form.get("message"), 4000)
        if len(company) < 2 or len(person) < 2 or not EMAIL_RE.match(email) or len(message) < 10 \
                or len(re.sub(r"\D", "", phone)) < 7:
            flash("Please complete every field with valid details.", "error")
        else:
            db = get_db()
            db.execute(
                "INSERT INTO employer_requests(company, contact_person, email, phone, message, created_at) VALUES (?,?,?,?,?,?)",
                (company, person, email, phone, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            db.commit()
            flash("Thank you! Our team will contact you shortly to confirm your vacancy.", "success")
        return redirect(url_for("employers") + "#form")
    return render_template("employers.html")


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        if request.form.get("website"):
            flash("Thank you!", "success")
            return redirect(url_for("contact") + "#form")
        name = clean(request.form.get("name"), 120)
        email = clean(request.form.get("email"), 160)
        subject = clean(request.form.get("subject"), 160)
        message = clean(request.form.get("message"), 4000)
        if len(name) < 2 or not EMAIL_RE.match(email) or len(subject) < 3 or len(message) < 10:
            flash("Please complete every field with valid details.", "error")
        else:
            db = get_db()
            db.execute("INSERT INTO messages(name, email, subject, message, created_at) VALUES (?,?,?,?,?)",
                       (name, email, subject, message, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            db.commit()
            flash("Message sent. We will reply as soon as we can.", "success")
        return redirect(url_for("contact") + "#form")
    return render_template("contact.html")


@app.errorhandler(404)
def not_found(_e):
    return render_template("error.html", code=404, title="Page not found",
                           text="The page you are looking for has moved or does not exist."), 404


@app.errorhandler(400)
def bad_request(e):
    return render_template("error.html", code=400, title="Something went wrong",
                           text=getattr(e, "description", "Bad request.")), 400


@app.errorhandler(413)
def too_large(_e):
    return render_template("error.html", code=413, title="File too large",
                           text="Please upload a CV smaller than 5 MB (the whole upload must stay under 6 MB)."), 413


# --------------------------------------------------------------------------- #
#  Admin (owner only)
# --------------------------------------------------------------------------- #
@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin_id"):
        return redirect(url_for("admin_dashboard"))
    if request.method == "POST":
        ip = request.remote_addr or "?"
        if too_many_attempts(ip):
            flash("Too many failed attempts. Please wait 10 minutes and try again.", "error")
            return render_template("admin/login.html")
        user = get_db().execute("SELECT * FROM admins WHERE username=?",
                                (clean(request.form.get("username"), 60),)).fetchone()
        if user and check_password_hash(user["password_hash"], request.form.get("password", "")):
            session.clear()
            session.permanent = True
            session["admin_id"] = user["id"]
            session["admin_name"] = user["username"]
            nxt = request.args.get("next", "")
            return redirect(nxt if nxt.startswith("/admin") else url_for("admin_dashboard"))
        record_failed(ip)
        flash("Incorrect username or password.", "error")
    return render_template("admin/login.html")


@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.route("/admin")
@login_required
def admin_dashboard():
    db = get_db()
    one = lambda sql: db.execute(sql).fetchone()[0]
    stats = {
        "open_jobs": one("SELECT COUNT(*) FROM jobs WHERE status='open'"),
        "total_jobs": one("SELECT COUNT(*) FROM jobs"),
        "applications": one("SELECT COUNT(*) FROM applications"),
        "new_apps": one("SELECT COUNT(*) FROM applications WHERE status='new'"),
        "requests": one("SELECT COUNT(*) FROM employer_requests WHERE status='new'"),
        "messages": one("SELECT COUNT(*) FROM messages WHERE is_read=0"),
    }
    recent = db.execute(
        """SELECT a.*, j.title AS job_title FROM applications a
           LEFT JOIN jobs j ON j.id = a.job_id ORDER BY a.id DESC LIMIT 6""").fetchall()
    top_jobs = db.execute(
        """SELECT j.id, j.title, COUNT(a.id) AS n FROM jobs j
           LEFT JOIN applications a ON a.job_id = j.id
           GROUP BY j.id ORDER BY n DESC, j.id DESC LIMIT 5""").fetchall()
    return render_template("admin/dashboard.html", stats=stats, recent=recent, top_jobs=top_jobs)


# ---- jobs ----
@app.route("/admin/jobs")
@login_required
def admin_jobs():
    rows = get_db().execute(
        """SELECT j.*, (SELECT COUNT(*) FROM applications a WHERE a.job_id=j.id) AS apps
           FROM jobs j ORDER BY j.id DESC""").fetchall()
    return render_template("admin/jobs.html", jobs=rows)


def read_job_form():
    data = {
        "title": clean(request.form.get("title"), 140),
        "company": clean(request.form.get("company"), 140),
        "location": clean(request.form.get("location"), 100),
        "category": clean(request.form.get("category"), 60),
        "job_type": clean(request.form.get("job_type"), 30),
        "salary": clean(request.form.get("salary"), 100),
        "description": clean(request.form.get("description"), 8000),
        "requirements": clean(request.form.get("requirements"), 4000),
        "deadline": clean(request.form.get("deadline"), 10),
        "featured": 1 if request.form.get("featured") else 0,
        "status": "closed" if request.form.get("status") == "closed" else "open",
    }
    error = None
    if not all([data["title"], data["company"], data["location"], data["description"]]):
        error = "Title, company, location and description are required."
    elif data["category"] not in CATEGORIES or data["job_type"] not in JOB_TYPES:
        error = "Please choose a valid category and job type."
    elif data["deadline"]:
        try:
            datetime.strptime(data["deadline"], "%Y-%m-%d")
        except ValueError:
            error = "The deadline date is not valid."
    return data, error


@app.route("/admin/jobs/new", methods=["GET", "POST"])
@login_required
def admin_job_new():
    if request.method == "POST":
        data, error = read_job_form()
        if error:
            flash(error, "error")
            return render_template("admin/job_form.html", job=data, mode="new")
        db = get_db()
        db.execute(
            """INSERT INTO jobs(title, company, location, category, job_type, salary, description,
               requirements, deadline, featured, status, created_at) VALUES
               (:title,:company,:location,:category,:job_type,:salary,:description,:requirements,
                :deadline,:featured,:status,:created)""",
            {**data, "created": datetime.now().strftime("%Y-%m-%d %H:%M:%S")})
        db.commit()
        flash("Job posted successfully.", "success")
        return redirect(url_for("admin_jobs"))
    return render_template("admin/job_form.html", job={"status": "open"}, mode="new")


@app.route("/admin/jobs/<int:job_id>/edit", methods=["GET", "POST"])
@login_required
def admin_job_edit(job_id):
    db = get_db()
    job = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        abort(404)
    if request.method == "POST":
        data, error = read_job_form()
        if error:
            flash(error, "error")
            return render_template("admin/job_form.html", job={**data, "id": job_id}, mode="edit")
        db.execute(
            """UPDATE jobs SET title=:title, company=:company, location=:location, category=:category,
               job_type=:job_type, salary=:salary, description=:description, requirements=:requirements,
               deadline=:deadline, featured=:featured, status=:status WHERE id=:id""",
            {**data, "id": job_id})
        db.commit()
        flash("Job updated.", "success")
        return redirect(url_for("admin_jobs"))
    return render_template("admin/job_form.html", job=job, mode="edit")


@app.route("/admin/jobs/<int:job_id>/toggle", methods=["POST"])
@login_required
def admin_job_toggle(job_id):
    db = get_db()
    db.execute("UPDATE jobs SET status = CASE status WHEN 'open' THEN 'closed' ELSE 'open' END WHERE id=?", (job_id,))
    db.commit()
    flash("Job status changed.", "success")
    return redirect(url_for("admin_jobs"))


@app.route("/admin/jobs/<int:job_id>/delete", methods=["POST"])
@login_required
def admin_job_delete(job_id):
    db = get_db()
    db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    db.commit()
    flash("Job deleted. Existing applications were kept.", "success")
    return redirect(url_for("admin_jobs"))


# ---- applications ----
@app.route("/admin/applications")
@login_required
def admin_applications():
    status = clean(request.args.get("status"), 20)
    job_id = request.args.get("job", "")
    q = clean(request.args.get("q"), 80)
    where, params = ["1=1"], []
    if status in APP_STATUSES:
        where.append("a.status=?")
        params.append(status)
    if job_id.isdigit():
        where.append("a.job_id=?")
        params.append(int(job_id))
    if q:
        where.append("(a.name LIKE ? OR a.email LIKE ? OR a.phone LIKE ?)")
        params += [f"%{q}%"] * 3
    db = get_db()
    rows = db.execute(
        f"""SELECT a.*, j.title AS job_title FROM applications a
            LEFT JOIN jobs j ON j.id=a.job_id WHERE {' AND '.join(where)} ORDER BY a.id DESC""",
        params).fetchall()
    job_list = db.execute("SELECT id, title FROM jobs ORDER BY title").fetchall()
    return render_template("admin/applications.html", apps=rows, sel_status=status,
                           sel_job=job_id, q=q, job_list=job_list)


@app.route("/admin/applications/<int:app_id>")
@login_required
def admin_application(app_id):
    row = get_db().execute(
        """SELECT a.*, j.title AS job_title FROM applications a
           LEFT JOIN jobs j ON j.id=a.job_id WHERE a.id=?""", (app_id,)).fetchone()
    if not row:
        abort(404)
    return render_template("admin/application.html", a=row)


@app.route("/admin/applications/<int:app_id>/status", methods=["POST"])
@login_required
def admin_application_status(app_id):
    status = request.form.get("status")
    if status in APP_STATUSES:
        db = get_db()
        db.execute("UPDATE applications SET status=? WHERE id=?", (status, app_id))
        db.commit()
        flash("Application marked as " + status + ".", "success")
    return redirect(request.form.get("back") if (request.form.get("back") or "").startswith("/admin")
                    else url_for("admin_applications"))


@app.route("/admin/applications/<int:app_id>/delete", methods=["POST"])
@login_required
def admin_application_delete(app_id):
    db = get_db()
    row = db.execute("SELECT cv_filename FROM applications WHERE id=?", (app_id,)).fetchone()
    if row:
        try:
            os.remove(os.path.join(CV_DIR, row["cv_filename"]))
        except OSError:
            pass
        db.execute("DELETE FROM applications WHERE id=?", (app_id,))
        db.commit()
        flash("Application deleted.", "success")
    return redirect(url_for("admin_applications"))


@app.route("/admin/cv/<int:app_id>")
@login_required
def admin_cv(app_id):
    row = get_db().execute("SELECT cv_filename, cv_original FROM applications WHERE id=?", (app_id,)).fetchone()
    if not row:
        abort(404)
    return send_from_directory(CV_DIR, row["cv_filename"], as_attachment=True,
                               download_name=row["cv_original"])


# ---- employer requests ----
@app.route("/admin/requests")
@login_required
def admin_requests():
    rows = get_db().execute("SELECT * FROM employer_requests ORDER BY id DESC").fetchall()
    return render_template("admin/requests.html", rows=rows)


@app.route("/admin/requests/<int:req_id>/<action>", methods=["POST"])
@login_required
def admin_request_action(req_id, action):
    db = get_db()
    if action == "done":
        db.execute("UPDATE employer_requests SET status='contacted' WHERE id=?", (req_id,))
    elif action == "delete":
        db.execute("DELETE FROM employer_requests WHERE id=?", (req_id,))
    else:
        abort(404)
    db.commit()
    flash("Employer request updated.", "success")
    return redirect(url_for("admin_requests"))


# ---- messages ----
@app.route("/admin/messages")
@login_required
def admin_messages():
    rows = get_db().execute("SELECT * FROM messages ORDER BY id DESC").fetchall()
    return render_template("admin/messages.html", rows=rows)


@app.route("/admin/messages/<int:msg_id>/<action>", methods=["POST"])
@login_required
def admin_message_action(msg_id, action):
    db = get_db()
    if action == "read":
        db.execute("UPDATE messages SET is_read=1 WHERE id=?", (msg_id,))
    elif action == "delete":
        db.execute("DELETE FROM messages WHERE id=?", (msg_id,))
    else:
        abort(404)
    db.commit()
    return redirect(url_for("admin_messages"))


# ---- settings ----
@app.route("/admin/settings", methods=["GET", "POST"])
@login_required
def admin_settings():
    db = get_db()
    if request.method == "POST":
        form_type = request.form.get("form_type")
        if form_type == "site":
            for key in ("site_name", "tagline", "email", "phone", "whatsapp", "address",
                        "hours", "facebook", "instagram", "linkedin"):
                db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
                           (key, clean(request.form.get(key), 200)))
            logo = request.files.get("logo")
            if logo and logo.filename:
                if allowed(logo.filename, ALLOWED_LOGO):
                    name = f"logo_{int(time.time())}_{secure_filename(logo.filename)}"
                    logo.save(os.path.join(LOGO_DIR, name))
                    db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('logo', ?)", (name,))
                else:
                    flash("Logo must be PNG, JPG, WEBP or SVG.", "error")
            if request.form.get("remove_logo"):
                db.execute("INSERT OR REPLACE INTO settings(key, value) VALUES ('logo', '')")
            db.commit()
            flash("Site settings saved.", "success")
        elif form_type == "password":
            admin = db.execute("SELECT * FROM admins WHERE id=?", (session["admin_id"],)).fetchone()
            current = request.form.get("current", "")
            new = request.form.get("new", "")
            if not check_password_hash(admin["password_hash"], current):
                flash("Your current password is not correct.", "error")
            elif len(new) < 8 or new != request.form.get("confirm", ""):
                flash("New password must be at least 8 characters and match the confirmation.", "error")
            else:
                db.execute("UPDATE admins SET password_hash=? WHERE id=?",
                           (generate_password_hash(new), admin["id"]))
                db.commit()
                flash("Password changed.", "success")
        return redirect(url_for("admin_settings"))
    return render_template("admin/settings.html")


@app.after_request
def security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    if request.path.startswith("/admin"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("DEBUG") == "1")
