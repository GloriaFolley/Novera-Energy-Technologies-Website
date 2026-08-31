import os
import sqlite3
import secrets
import smtplib

from pathlib import Path
from functools import wraps
from datetime import datetime, timezone
from email.message import EmailMessage

from dotenv import load_dotenv

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    abort,
    send_from_directory,
    jsonify
)

from werkzeug.security import (
    generate_password_hash,
    check_password_hash
)


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

# Actual Novera project
PROJECT_DIR = Path("/home/gloria/novera")

# Correct assets directory
ASSETS_DIR = PROJECT_DIR / "assets"

# Correct logo path
LOGO_PATH = ASSETS_DIR / "logo.jpg"

TEMPLATES_DIR = BASE_DIR / "templates"

ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)


# ============================================================
# FLASK CONFIGURATION
# ============================================================

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR)
)

app.secret_key = os.getenv(
    "SECRET_KEY",
    secrets.token_hex(32)
)

app.config["SESSION_COOKIE_HTTPONLY"] = True

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

app.config["SESSION_COOKIE_SECURE"] = (
    os.getenv(
        "SESSION_COOKIE_SECURE",
        "False"
    ).lower() == "true"
)


# ============================================================
# COMPANY CONFIGURATION
# ============================================================

COMPANY_NAME = os.getenv(
    "COMPANY_NAME",
    "Novera Energy & Technologies"
)

COMPANY_TAGLINE = os.getenv(
    "COMPANY_TAGLINE",
    "Light · Motion · Intelligence"
)

COMPANY_EMAIL_DOMAIN = os.getenv(
    "COMPANY_EMAIL_DOMAIN",
    "novera.com"
)


# ============================================================
# DATABASE CONFIGURATION
# ============================================================

DATABASE_PATH_ENV = os.getenv(
    "DATABASE_PATH",
    ""
).strip()

if DATABASE_PATH_ENV:

    DATABASE_PATH = Path(
        DATABASE_PATH_ENV
    )

    if not DATABASE_PATH.is_absolute():

        DATABASE_PATH = BASE_DIR / DATABASE_PATH

else:

    DATABASE_PATH = BASE_DIR / "novera.db"


# ============================================================
# ADMIN CONFIGURATION
# ============================================================

ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL",
    "admin@novera.com"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "ChangeThisPassword123!"
)


# ============================================================
# MD REGISTRATION KEY
# ============================================================

MD_REGISTRATION_KEY = os.getenv(
    "MD_REGISTRATION_KEY",
    ""
)


# ============================================================
# EMAIL CONFIGURATION
# ============================================================

SMTP_HOST = os.getenv(
    "SMTP_HOST",
    ""
).strip()

SMTP_PORT = int(
    os.getenv(
        "SMTP_PORT",
        "587"
    )
)

SMTP_USERNAME = os.getenv(
    "SMTP_USERNAME",
    ""
).strip()

SMTP_PASSWORD = os.getenv(
    "SMTP_PASSWORD",
    ""
).strip()

SMTP_USE_TLS = (
    os.getenv(
        "SMTP_USE_TLS",
        "True"
    ).lower() == "true"
)

MAIL_FROM = os.getenv(
    "MAIL_FROM",
    SMTP_USERNAME
).strip()


# ============================================================
# CONSULTATION EMAIL
# ============================================================

CONSULTATION_EMAIL = os.getenv(
    "CONSULTATION_EMAIL",
    "noveratech001@gmail.com"
).strip()


# ============================================================
# DATABASE CONNECTION
# ============================================================

def get_db():

    db = sqlite3.connect(
        str(DATABASE_PATH)
    )

    db.row_factory = sqlite3.Row

    # Helps SQLite handle concurrent portal requests better
    db.execute(
        "PRAGMA foreign_keys = ON"
    )

    return db


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    DATABASE_PATH.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    db = get_db()

    db.executescript(
        """

        CREATE TABLE IF NOT EXISTS staff (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            staff_id TEXT UNIQUE NOT NULL,

            first_name TEXT NOT NULL,

            last_name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            phone TEXT NOT NULL,

            department TEXT NOT NULL,

            position TEXT NOT NULL,

            password_hash TEXT NOT NULL,

            status TEXT NOT NULL DEFAULT 'Pending',

            created_at TEXT NOT NULL,

            approved_at TEXT,

            last_login TEXT

        );


        CREATE TABLE IF NOT EXISTS md (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            first_name TEXT NOT NULL,

            last_name TEXT NOT NULL,

            email TEXT UNIQUE NOT NULL,

            phone TEXT NOT NULL,

            password_hash TEXT NOT NULL,

            status TEXT NOT NULL DEFAULT 'Active',

            created_at TEXT NOT NULL,

            last_login TEXT

        );


        CREATE TABLE IF NOT EXISTS consultations (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            name TEXT NOT NULL,

            email TEXT,

            phone TEXT,

            company TEXT,

            service TEXT,

            message TEXT,

            status TEXT NOT NULL DEFAULT 'New',

            created_at TEXT NOT NULL,

            assigned_staff_id INTEGER

        );


        CREATE TABLE IF NOT EXISTS activity_logs (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            actor TEXT,

            action TEXT,

            details TEXT,

            created_at TEXT NOT NULL

        );

        """
    )

    db.commit()
    db.close()


# ============================================================
# DATABASE MIGRATION
# ============================================================

def migrate_database():

    db = get_db()

    # --------------------------------------------------------
    # CONSULTATIONS
    # --------------------------------------------------------

    columns = db.execute(
        """
        PRAGMA table_info(consultations)
        """
    ).fetchall()

    column_names = [
        column["name"]
        for column in columns
    ]

    if "assigned_staff_id" not in column_names:

        db.execute(
            """
            ALTER TABLE consultations
            ADD COLUMN assigned_staff_id INTEGER
            """
        )

        print(
            "Added assigned_staff_id to consultations."
        )

    db.commit()

    # --------------------------------------------------------
    # STAFF
    # --------------------------------------------------------

    staff_columns = db.execute(
        """
        PRAGMA table_info(staff)
        """
    ).fetchall()

    staff_column_names = [
        column["name"]
        for column in staff_columns
    ]

    print()
    print("=" * 70)
    print("DATABASE CHECK")
    print("=" * 70)

    print(
        f"Database: {DATABASE_PATH}"
    )

    print(
        f"Consultations assigned_staff_id exists: "
        f"{'assigned_staff_id' in column_names}"
    )

    print(
        f"Staff table exists: "
        f"{len(staff_column_names) > 0}"
    )

    print("=" * 70)
    print()

    db.close()


# ============================================================
# INITIALIZE DATABASE
# ============================================================

init_db()
migrate_database()


# ============================================================
# TEMPLATE GLOBALS
# ============================================================

@app.context_processor
def inject_company():

    return {

        "company_name":
            COMPANY_NAME,

        "company_tagline":
            COMPANY_TAGLINE,

        "logo_url":
            url_for("logo"),

        "logo_asset_url":
            url_for(
                "assets",
                filename="logo.jpg"
            )
    }


# ============================================================
# LOGO ROUTE
# ============================================================

@app.route("/logo.jpg")
def logo():

    print(
        f"Logo requested: {LOGO_PATH}"
    )

    if not LOGO_PATH.exists():

        print()
        print("=" * 70)
        print("NOVERA LOGO NOT FOUND")
        print("=" * 70)

        print(
            f"Expected logo:"
        )

        print(
            LOGO_PATH
        )

        print(
            f"Assets directory:"
        )

        print(
            ASSETS_DIR
        )

        print(
            f"Assets directory exists:"
        )

        print(
            ASSETS_DIR.exists()
        )

        print(
            f"Logo exists:"
        )

        print(
            LOGO_PATH.exists()
        )

        print("=" * 70)
        print()

        return (
            "Novera logo not found.",
            404
        )

    return send_from_directory(
        str(ASSETS_DIR),
        LOGO_FILENAME
        if "LOGO_FILENAME" in globals()
        else "logo.jpg"
    )


# ============================================================
# ASSETS ROUTE
# ============================================================

@app.route("/assets/<path:filename>")
def assets(filename):

    file_path = ASSETS_DIR / filename

    if (
        not file_path.exists()
        or not file_path.is_file()
    ):

        abort(404)

    return send_from_directory(
        str(ASSETS_DIR),
        filename
    )


# ============================================================
# PUBLIC WEBSITE
# ============================================================

@app.route("/")
def index():

    index_file = ASSETS_DIR / "index.html"

    if index_file.exists():

        return send_from_directory(
            str(ASSETS_DIR),
            "index.html"
        )

    return render_template(
        "index.html"
    )


# ============================================================
# PUBLIC WEBSITE FILES
# ============================================================

@app.route("/<path:filename>")
def public_files(filename):

    blocked = (
        "staff/",
        "admin/",
        "md/",
        "api/"
    )

    if filename.startswith(blocked):

        abort(404)

    file_path = ASSETS_DIR / filename

    if (
        file_path.exists()
        and file_path.is_file()
    ):

        return send_from_directory(
            str(ASSETS_DIR),
            filename
        )

    abort(404)


# ============================================================
# STAFF ID GENERATOR
# ============================================================

def generate_staff_id():

    year = datetime.now().year

    db = get_db()

    rows = db.execute(
        """
        SELECT staff_id
        FROM staff
        WHERE staff_id LIKE ?
        ORDER BY id DESC
        """,
        (
            f"NVR-{year}-%",
        )
    ).fetchall()

    db.close()

    if not rows:

        number = 1

    else:

        highest = 0

        for row in rows:

            try:

                current = int(
                    row["staff_id"]
                    .split("-")[-1]
                )

                highest = max(
                    highest,
                    current
                )

            except (
                ValueError,
                IndexError
            ):

                continue

        number = highest + 1

    return (
        f"NVR-{year}-{number:04d}"
    )


# ============================================================
# CLEAN NAME
# ============================================================

def clean_name(value):

    value = value.strip().lower()

    return "".join(
        char
        for char in value
        if char.isalnum()
    )


# ============================================================
# WORK EMAIL GENERATOR
# ============================================================

def generate_work_email(
    first_name,
    last_name
):

    first = clean_name(
        first_name
    )

    last = clean_name(
        last_name
    )

    base = (
        f"{first}.{last}"
    )

    email = (
        f"{base}@"
        f"{COMPANY_EMAIL_DOMAIN}"
    )

    db = get_db()

    counter = 2

    while db.execute(
        """
        SELECT id
        FROM staff
        WHERE email = ?
        """,
        (email,)
    ).fetchone():

        email = (
            f"{base}{counter}@"
            f"{COMPANY_EMAIL_DOMAIN}"
        )

        counter += 1

    db.close()

    return email


# ============================================================
# ACTIVITY LOG
# ============================================================

def log_activity(
    actor,
    action,
    details
):

    try:

        db = get_db()

        db.execute(
            """
            INSERT INTO activity_logs
            (
                actor,
                action,
                details,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                actor,
                action,
                details,
                datetime.now(
                    timezone.utc
                ).isoformat()
            )
        )

        db.commit()
        db.close()

    except Exception as error:

        print(
            f"Activity log error: {error}"
        )


# ============================================================
# EMAIL FUNCTION
# ============================================================

def send_email(
    recipient,
    subject,
    body
):

    print()
    print("=" * 70)
    print("NOVERA EMAIL")
    print("=" * 70)

    print(
        f"SMTP Host: {SMTP_HOST}"
    )

    print(
        f"SMTP Port: {SMTP_PORT}"
    )

    print(
        f"SMTP Username: {SMTP_USERNAME}"
    )

    print(
        f"Recipient: {recipient}"
    )

    print(
        f"Subject: {subject}"
    )

    if not SMTP_HOST:

        print(
            "ERROR: SMTP_HOST is empty."
        )

        return False

    if not SMTP_USERNAME:

        print(
            "ERROR: SMTP_USERNAME is empty."
        )

        return False

    if not SMTP_PASSWORD:

        print(
            "ERROR: SMTP_PASSWORD is empty."
        )

        return False

    if not recipient:

        print(
            "ERROR: Recipient is empty."
        )

        return False

    try:

        message = EmailMessage()

        message["From"] = MAIL_FROM

        message["To"] = recipient

        message["Subject"] = subject

        message.set_content(body)

        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=30
        ) as server:

            server.ehlo()

            if SMTP_USE_TLS:

                server.starttls()

                server.ehlo()

            server.login(
                SMTP_USERNAME,
                SMTP_PASSWORD
            )

            server.send_message(
                message
            )

        print(
            "EMAIL SENT SUCCESSFULLY"
        )

        print("=" * 70)

        return True

    except Exception as error:

        print(
            "EMAIL ERROR:"
        )

        print(
            str(error)
        )

        print("=" * 70)

        return False


# ============================================================
# REGISTRATION EMAIL
# ============================================================

def send_registration_email(
    first_name,
    staff_id,
    email
):

    subject = (
        f"{COMPANY_NAME} - "
        "Staff Registration"
    )

    body = f"""
Dear {first_name},

Your staff registration with
{COMPANY_NAME} has been received.

Staff ID:
{staff_id}

Official Work Email:
{email}

Your account is currently pending
administrator approval.

Regards,

{COMPANY_NAME}
Staff Administration
"""

    return send_email(
        email,
        subject,
        body
    )


# ============================================================
# APPROVAL EMAIL
# ============================================================

def send_approval_email(
    first_name,
    staff_id,
    email
):

    subject = (
        f"{COMPANY_NAME} - "
        "Staff Account Approved"
    )

    body = f"""
Dear {first_name},

Your {COMPANY_NAME} staff account
has been approved.

Staff ID:
{staff_id}

Official Work Email:
{email}

You can now access the Novera
Staff Portal.

Regards,

{COMPANY_NAME}
Staff Administration
"""

    return send_email(
        email,
        subject,
        body
    )


# ============================================================
# CONSULTATION NOTIFICATION
# ============================================================

def send_consultation_notification(
    consultation_id,
    name,
    email,
    phone,
    company,
    service,
    message
):

    body = f"""
NEW NOVERA CONSULTATION REQUEST
================================

Consultation ID:
#{consultation_id}

Name:
{name}

Email:
{email or 'Not provided'}

Phone:
{phone or 'Not provided'}

Company:
{company or 'Not provided'}

Service:
{service}

Message:
{message or 'No message provided'}

================================

This consultation has been added
to the Novera Consultation Management Portal.

{COMPANY_NAME}
"""

    return send_email(
        CONSULTATION_EMAIL,
        (
            f"New Consultation Request "
            f"#{consultation_id} - {service}"
        ),
        body
    )


# ============================================================
# ASSIGNMENT EMAIL
# ============================================================

def send_assignment_email(
    staff,
    consultation
):

    subject = (
        f"{COMPANY_NAME} - "
        f"Consultation #{consultation['id']} "
        "Assigned"
    )

    body = f"""
Dear {staff['first_name']},

A consultation request has been
assigned to you.

================================
CONSULTATION DETAILS
================================

Consultation ID:
#{consultation['id']}

Client:
{consultation['name']}

Email:
{consultation['email'] or 'Not provided'}

Phone:
{consultation['phone'] or 'Not provided'}

Company:
{consultation['company'] or 'Not provided'}

Service:
{consultation['service']}

Message:
{consultation['message'] or 'No message provided'}

================================

Please log in to the Novera Staff Portal
to review this consultation.

Regards,

{COMPANY_NAME}
"""

    return send_email(
        staff["email"],
        subject,
        body
    )


# ============================================================
# STAFF AUTH
# ============================================================

def staff_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get("staff_id"):

            flash(
                "Please log in to access the staff portal.",
                "warning"
            )

            return redirect(
                url_for("staff_login")
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# ============================================================
# ADMIN AUTH
# ============================================================

def admin_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get(
            "admin_logged_in"
        ):

            flash(
                "Administrator login required.",
                "warning"
            )

            return redirect(
                url_for("admin_login")
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# ============================================================
# MD AUTH
# ============================================================

def md_required(function):

    @wraps(function)
    def wrapper(*args, **kwargs):

        if not session.get(
            "md_logged_in"
        ):

            flash(
                "MD login required.",
                "warning"
            )

            return redirect(
                url_for("md_login")
            )

        return function(
            *args,
            **kwargs
        )

    return wrapper


# ============================================================
# STAFF REGISTRATION
# ============================================================

@app.route(
    "/staff/register",
    methods=["GET", "POST"]
)
def staff_register():

    if request.method == "GET":

        return render_template(
            "staff_register.html"
        )

    first_name = request.form.get(
        "first_name",
        ""
    ).strip()

    last_name = request.form.get(
        "last_name",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    department = request.form.get(
        "department",
        ""
    ).strip()

    position = request.form.get(
        "position",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    if not all(
        [
            first_name,
            last_name,
            phone,
            department,
            position,
            password,
            confirm_password
        ]
    ):

        flash(
            "Please complete all required fields.",
            "danger"
        )

        return render_template(
            "staff_register.html"
        )

    if len(password) < 8:

        flash(
            "Password must contain at least 8 characters.",
            "danger"
        )

        return render_template(
            "staff_register.html"
        )

    if password != confirm_password:

        flash(
            "Passwords do not match.",
            "danger"
        )

        return render_template(
            "staff_register.html"
        )

    staff_id = generate_staff_id()

    email = generate_work_email(
        first_name,
        last_name
    )

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    db = get_db()

    try:

        db.execute(
            """
            INSERT INTO staff
            (
                staff_id,
                first_name,
                last_name,
                email,
                phone,
                department,
                position,
                password_hash,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                staff_id,
                first_name,
                last_name,
                email,
                phone,
                department,
                position,
                generate_password_hash(
                    password
                ),
                "Pending",
                created_at
            )
        )

        db.commit()

    except sqlite3.IntegrityError:

        db.rollback()
        db.close()

        flash(
            "Unable to create this account. Please try again.",
            "danger"
        )

        return redirect(
            url_for("staff_register")
        )

    db.close()

    send_registration_email(
        first_name,
        staff_id,
        email
    )

    log_activity(
        "Public Registration",
        "Staff Registration",
        f"{staff_id} registered"
    )

    return render_template(
        "registration_success.html",
        staff={
            "staff_id": staff_id,
            "email": email
        }
    )


# ============================================================
# STAFF LOGIN
# ============================================================

@app.route(
    "/staff/login",
    methods=["GET", "POST"]
)
def staff_login():

    if session.get("staff_id"):

        return redirect(
            url_for("staff_dashboard")
        )

    if request.method == "GET":

        return render_template(
            "staff_login.html"
        )

    login = request.form.get(
        "login",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    db = get_db()

    staff = db.execute(
        """
        SELECT *
        FROM staff
        WHERE LOWER(staff_id) = ?
        OR LOWER(email) = ?
        LIMIT 1
        """,
        (
            login,
            login
        )
    ).fetchone()

    if staff is None:

        db.close()

        flash(
            "Invalid Staff ID/email or password.",
            "danger"
        )

        return render_template(
            "staff_login.html"
        )

    if not check_password_hash(
        staff["password_hash"],
        password
    ):

        db.close()

        flash(
            "Invalid Staff ID/email or password.",
            "danger"
        )

        return render_template(
            "staff_login.html"
        )

    if staff["status"] == "Pending":

        db.close()

        flash(
            "Your account is awaiting administrator approval.",
            "warning"
        )

        return render_template(
            "staff_login.html"
        )

    if staff["status"] == "Rejected":

        db.close()

        flash(
            "Your staff registration was rejected.",
            "danger"
        )

        return render_template(
            "staff_login.html"
        )

    if staff["status"] == "Disabled":

        db.close()

        flash(
            "Your staff account has been disabled.",
            "danger"
        )

        return render_template(
            "staff_login.html"
        )

    db.execute(
        """
        UPDATE staff
        SET last_login = ?
        WHERE id = ?
        """,
        (
            datetime.now(
                timezone.utc
            ).isoformat(),
            staff["id"]
        )
    )

    db.commit()

    db.close()

    session.clear()

    # IMPORTANT:
    # The session stores the permanent NVR staff ID,
    # not the temporary SQLite database ID.
    session["staff_id"] = staff["staff_id"]

    return redirect(
        url_for("staff_dashboard")
    )


# ============================================================
# STAFF DASHBOARD
# ============================================================

@app.route("/staff/dashboard")
@staff_required
def staff_dashboard():

    db = get_db()

    # ========================================================
    # GET LOGGED-IN STAFF
    # ========================================================

    staff = db.execute(
        """
        SELECT *
        FROM staff
        WHERE staff_id = ?
        """,
        (
            session["staff_id"],
        )
    ).fetchone()

    if staff is None:

        db.close()

        session.clear()

        flash(
            "Staff account could not be found.",
            "danger"
        )

        return redirect(
            url_for("staff_login")
        )

    # ========================================================
    # GET ASSIGNED CONSULTATIONS
    # ========================================================

    assigned_requests = db.execute(
        """
        SELECT
            c.*,

            s.staff_id AS assigned_staff_id,

            s.first_name AS assigned_first_name,

            s.last_name AS assigned_last_name,

            s.email AS assigned_staff_email,

            s.department AS assigned_department,

            s.position AS assigned_position

        FROM consultations c

        LEFT JOIN staff s
            ON s.id = c.assigned_to

        WHERE c.assigned_to = ?

        ORDER BY c.id DESC
        """,
        (
            staff["id"],
        )
    ).fetchall()

    # ========================================================
    # STATISTICS
    # ========================================================

    assigned_count = len(assigned_requests)

    in_progress_count = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE assigned_to = ?
        AND LOWER(REPLACE(status, '_', ' ')) = 'in progress'
        """,
        (
            staff["id"],
        )
    ).fetchone()[0]

    completed_count = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE assigned_to = ?
        AND LOWER(status) = 'completed'
        """,
        (
            staff["id"],
        )
    ).fetchone()[0]

    pending_count = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE assigned_to = ?
        AND (
            LOWER(status) = 'new'
            OR LOWER(status) = 'pending'
        )
        """,
        (
            staff["id"],
        )
    ).fetchone()[0]

    db.close()

    # ========================================================
    # DASHBOARD
    # ========================================================

    return render_template(
        "staff_dashboard.html",

        staff=staff,

        assigned_requests=assigned_requests,

        assigned_count=assigned_count,

        pending_count=pending_count,

        in_progress_count=in_progress_count,

        completed_count=completed_count
    )

# ============================================================
# STAFF LOGOUT
# ============================================================

@app.route("/staff/logout")
def staff_logout():

    session.pop(
        "staff_id",
        None
    )

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("staff_login")
    )


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

    if session.get(
        "admin_logged_in"
    ):

        return redirect(
            url_for("admin_dashboard")
        )

    if request.method == "GET":

        return render_template(
            "admin_login.html"
        )

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    if (
        email == ADMIN_EMAIL.lower()
        and password == ADMIN_PASSWORD
    ):

        session.clear()

        session["admin_logged_in"] = True

        session["admin_email"] = ADMIN_EMAIL

        log_activity(
            ADMIN_EMAIL,
            "Admin Login",
            "Administrator logged in"
        )

        return redirect(
            url_for("admin_dashboard")
        )

    flash(
        "Invalid administrator credentials.",
        "danger"
    )

    return render_template(
        "admin_login.html"
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    db = get_db()

    total_staff = db.execute(
        "SELECT COUNT(*) FROM staff"
    ).fetchone()[0]

    active_staff = db.execute(
        """
        SELECT COUNT(*)
        FROM staff
        WHERE status = 'Active'
        """
    ).fetchone()[0]

    pending_staff = db.execute(
        """
        SELECT COUNT(*)
        FROM staff
        WHERE status = 'Pending'
        """
    ).fetchone()[0]

    disabled_staff = db.execute(
        """
        SELECT COUNT(*)
        FROM staff
        WHERE status = 'Disabled'
        """
    ).fetchone()[0]

    rejected_staff = db.execute(
        """
        SELECT COUNT(*)
        FROM staff
        WHERE status = 'Rejected'
        """
    ).fetchone()[0]

    total_consultations = db.execute(
        "SELECT COUNT(*) FROM consultations"
    ).fetchone()[0]

    new_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE status = 'New'
        """
    ).fetchone()[0]

    in_progress_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE status = 'In Progress'
        """
    ).fetchone()[0]

    closed_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE status = 'Closed'
        """
    ).fetchone()[0]

    unassigned_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE assigned_staff_id IS NULL
        """
    ).fetchone()[0]

    assigned_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE assigned_staff_id IS NOT NULL
        """
    ).fetchone()[0]

    recent_consultations = db.execute(
        """
        SELECT
            consultations.*,

            staff.first_name
                AS assigned_first_name,

            staff.last_name
                AS assigned_last_name,

            staff.staff_id
                AS assigned_staff_code

        FROM consultations

        LEFT JOIN staff
            ON consultations.assigned_staff_id = staff.id

        ORDER BY consultations.id DESC

        LIMIT 10
        """
    ).fetchall()

    recent_staff = db.execute(
        """
        SELECT *
        FROM staff
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    db.close()

    return render_template(
        "admin_dashboard.html",

        total_staff=total_staff,

        active_staff=active_staff,

        pending_staff=pending_staff,

        disabled_staff=disabled_staff,

        rejected_staff=rejected_staff,

        total_consultations=
            total_consultations,

        new_consultations=
            new_consultations,

        in_progress_consultations=
            in_progress_consultations,

        closed_consultations=
            closed_consultations,

        unassigned_consultations=
            unassigned_consultations,

        assigned_consultations=
            assigned_consultations,

        recent_consultations=
            recent_consultations,

        recent_staff=
            recent_staff
    )


# ============================================================
# ADMIN STAFF
# ============================================================

@app.route("/admin/staff")
@admin_required
def admin_staff():

    db = get_db()

    staff = db.execute(
        """
        SELECT *
        FROM staff
        ORDER BY id DESC
        """
    ).fetchall()

    db.close()

    return render_template(
        "admin_staff.html",
        staff=staff
    )


# ============================================================
# ADMIN VIEW STAFF
# ============================================================

@app.route(
    "/admin/staff/<int:staff_db_id>"
)
@admin_required
def admin_view_staff(
    staff_db_id
):

    db = get_db()

    staff = db.execute(
        """
        SELECT *
        FROM staff
        WHERE id = ?
        """,
        (
            staff_db_id,
        )
    ).fetchone()

    db.close()

    if staff is None:

        abort(404)

    return render_template(
        "admin_view_staff.html",
        staff=staff
    )


# ============================================================
# ADMIN STAFF ACTION
# ============================================================

@app.route(
    "/admin/staff/<int:staff_db_id>/<action>",
    methods=["POST"]
)
@admin_required
def admin_staff_action(
    staff_db_id,
    action
):

    allowed_actions = (
        "approve",
        "reject",
        "disable",
        "activate"
    )

    if action not in allowed_actions:

        abort(400)

    db = get_db()

    staff = db.execute(
        """
        SELECT *
        FROM staff
        WHERE id = ?
        """,
        (
            staff_db_id,
        )
    ).fetchone()

    if staff is None:

        db.close()

        abort(404)

    if action == "approve":

        db.execute(
            """
            UPDATE staff
            SET status = 'Active',
                approved_at = ?
            WHERE id = ?
            """,
            (
                datetime.now(
                    timezone.utc
                ).isoformat(),
                staff_db_id
            )
        )

        message = (
            f"{staff['first_name']} "
            f"{staff['last_name']} "
            "has been approved."
        )

        category = "success"

        send_approval_email(
            staff["first_name"],
            staff["staff_id"],
            staff["email"]
        )

    elif action == "reject":

        db.execute(
            """
            UPDATE staff
            SET status = 'Rejected'
            WHERE id = ?
            """,
            (
                staff_db_id,
            )
        )

        message = (
            f"{staff['first_name']} "
            f"{staff['last_name']} "
            "has been rejected."
        )

        category = "warning"

    elif action == "disable":

        db.execute(
            """
            UPDATE staff
            SET status = 'Disabled'
            WHERE id = ?
            """,
            (
                staff_db_id,
            )
        )

        message = (
            "Staff account has been disabled."
        )

        category = "warning"

    else:

        db.execute(
            """
            UPDATE staff
            SET status = 'Active'
            WHERE id = ?
            """,
            (
                staff_db_id,
            )
        )

        message = (
            "Staff account has been activated."
        )

        category = "success"

    db.commit()

    db.close()

    log_activity(
        ADMIN_EMAIL,
        f"Staff {action}",
        f"Staff database ID: {staff_db_id}"
    )

    flash(
        message,
        category
    )

    return redirect(
        url_for(
            "admin_view_staff",
            staff_db_id=staff_db_id
        )
    )


# ============================================================
# ADMIN CONSULTATION MANAGEMENT
# ============================================================

def ensure_consultation_columns():
    """
    Safely adds consultation management columns to an existing
    Novera database without deleting existing consultation data.
    """

    db = get_db()

    columns = {
        row["name"]
        for row in db.execute(
            "PRAGMA table_info(consultations)"
        ).fetchall()
    }

    # Staff assignment
    if "assigned_to" not in columns:
        db.execute(
            """
            ALTER TABLE consultations
            ADD COLUMN assigned_to INTEGER
            """
        )

    # Last update timestamp
    if "updated_at" not in columns:
        db.execute(
            """
            ALTER TABLE consultations
            ADD COLUMN updated_at TEXT
            """
        )

    db.commit()
    db.close()


def get_consultation(consultation_id):
    """
    Retrieve one consultation together with the assigned staff member.
    """

    ensure_consultation_columns()

    db = get_db()

    consultation = db.execute(
        """
        SELECT
            c.*,

            s.id AS assigned_staff_id,
            s.staff_id AS assigned_staff_code,
            s.first_name AS assigned_first_name,
            s.last_name AS assigned_last_name,
            s.email AS assigned_staff_email,
            s.phone AS assigned_staff_phone,
            s.department AS assigned_department,
            s.position AS assigned_position,
            s.status AS assigned_staff_status

        FROM consultations c

        LEFT JOIN staff s
            ON s.id = c.assigned_to

        WHERE c.id = ?

        LIMIT 1
        """,
        (consultation_id,)
    ).fetchone()

    db.close()

    return consultation


def get_assignable_staff():
    """
    Return staff members who can be assigned consultation requests.
    """

    db = get_db()

    staff = db.execute(
        """
        SELECT
            id,
            staff_id,
            first_name,
            last_name,
            email,
            department,
            position,
            status
        FROM staff
        WHERE status = 'Active'
        ORDER BY first_name ASC, last_name ASC
        """
    ).fetchall()

    db.close()

    return staff


# ============================================================
# ADMIN CONSULTATIONS LIST
# ============================================================

@app.route("/admin/consultations")
@admin_required
def admin_consultations():

    ensure_consultation_columns()

    db = get_db()

    consultations = db.execute(
        """
        SELECT
            c.*,

            s.first_name AS assigned_first_name,
            s.last_name AS assigned_last_name,
            s.staff_id AS assigned_staff_code,
            s.department AS assigned_department

        FROM consultations c

        LEFT JOIN staff s
            ON s.id = c.assigned_to

        ORDER BY c.id DESC
        """
    ).fetchall()

    # Statistics
    total_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        """
    ).fetchone()[0]

    new_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE LOWER(status) = 'new'
        """
    ).fetchone()[0]

    in_progress_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE LOWER(status) IN (
            'in progress',
            'processing'
        )
        """
    ).fetchone()[0]

    completed_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE LOWER(status) IN (
            'completed',
            'closed'
        )
        """
    ).fetchone()[0]

    db.close()

    return render_template(
        "admin_consultations.html",
        consultations=consultations,
        total_consultations=total_consultations,
        new_consultations=new_consultations,
        in_progress_consultations=in_progress_consultations,
        completed_consultations=completed_consultations
    )


# ============================================================
# ADMIN VIEW CONSULTATION
# ============================================================

@app.route(
    "/admin/consultation/<int:consultation_id>"
)
@admin_required
def admin_view_consultation(consultation_id):

    consultation = get_consultation(
        consultation_id
    )

    if consultation is None:
        flash(
            "Consultation request not found.",
            "danger"
        )

        return redirect(
            url_for("admin_consultations")
        )

    staff = get_assignable_staff()

    return render_template(
        "admin_view_consultation.html",
        request=consultation,
        staff=staff
    )


# ============================================================
# ADMIN UPDATE CONSULTATION
# ============================================================

@app.route(
    "/admin/consultation/<int:consultation_id>/update",
    methods=["POST"]
)
@admin_required
def update_admin_consultation(
    consultation_id
):

    ensure_consultation_columns()

    name = request.form.get(
        "name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    company = request.form.get(
        "company",
        ""
    ).strip()

    service = request.form.get(
        "service",
        ""
    ).strip()

    message = request.form.get(
        "message",
        ""
    ).strip()

    status = request.form.get(
        "status",
        "New"
    ).strip()

    allowed_statuses = (
        "New",
        "In Progress",
        "Completed",
        "Closed",
        "Cancelled"
    )

    if status not in allowed_statuses:
        status = "New"

    if not name:
        flash(
            "Client name is required.",
            "danger"
        )

        return redirect(
            url_for(
                "admin_view_consultation",
                consultation_id=consultation_id
            )
        )

    if not service:
        flash(
            "Service is required.",
            "danger"
        )

        return redirect(
            url_for(
                "admin_view_consultation",
                consultation_id=consultation_id
            )
        )

    db = get_db()

    consultation = db.execute(
        """
        SELECT id
        FROM consultations
        WHERE id = ?
        """,
        (consultation_id,)
    ).fetchone()

    if consultation is None:
        db.close()

        flash(
            "Consultation request not found.",
            "danger"
        )

        return redirect(
            url_for("admin_consultations")
        )

    updated_at = datetime.now(
        timezone.utc
    ).isoformat()

    db.execute(
        """
        UPDATE consultations

        SET
            name = ?,
            email = ?,
            phone = ?,
            company = ?,
            service = ?,
            message = ?,
            status = ?,
            updated_at = ?

        WHERE id = ?
        """,
        (
            name,
            email,
            phone,
            company,
            service,
            message,
            status,
            updated_at,
            consultation_id
        )
    )

    db.commit()
    db.close()

    flash(
        "Consultation request updated successfully.",
        "success"
    )

    return redirect(
        url_for(
            "admin_view_consultation",
            consultation_id=consultation_id
        )
    )


# ============================================================
# ADMIN CHANGE CONSULTATION STATUS
# ============================================================

@app.route(
    "/admin/consultation/<int:consultation_id>/status",
    methods=["POST"]
)
@admin_required
def update_consultation_status(
    consultation_id
):

    ensure_consultation_columns()

    status = request.form.get(
        "status",
        "New"
    ).strip()

    allowed_statuses = (
        "New",
        "In Progress",
        "Completed",
        "Closed",
        "Cancelled"
    )

    if status not in allowed_statuses:
        status = "New"

    db = get_db()

    consultation = db.execute(
        """
        SELECT id
        FROM consultations
        WHERE id = ?
        """,
        (consultation_id,)
    ).fetchone()

    if consultation is None:
        db.close()

        flash(
            "Consultation request not found.",
            "danger"
        )

        return redirect(
            url_for("admin_consultations")
        )

    updated_at = datetime.now(
        timezone.utc
    ).isoformat()

    db.execute(
        """
        UPDATE consultations
        SET
            status = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            status,
            updated_at,
            consultation_id
        )
    )

    db.commit()
    db.close()

    flash(
        "Consultation status updated.",
        "success"
    )

    return redirect(
        url_for(
            "admin_view_consultation",
            consultation_id=consultation_id
        )
    )


# ============================================================
# ADMIN ASSIGN CONSULTATION
# ============================================================

@app.route(
    "/admin/consultation/<int:consultation_id>/assign",
    methods=["POST"]
)
@admin_required
def assign_admin_consultation(
    consultation_id
):

    ensure_consultation_columns()

    assigned_to = request.form.get(
        "assigned_to",
        ""
    ).strip()

    if assigned_to:
        try:
            assigned_to = int(
                assigned_to
            )
        except ValueError:
            assigned_to = None
    else:
        assigned_to = None

    db = get_db()

    consultation = db.execute(
        """
        SELECT *
        FROM consultations
        WHERE id = ?
        """,
        (consultation_id,)
    ).fetchone()

    if consultation is None:
        db.close()

        flash(
            "Consultation request not found.",
            "danger"
        )

        return redirect(
            url_for("admin_consultations")
        )

    staff_member = None

    if assigned_to is not None:

        staff_member = db.execute(
            """
            SELECT *
            FROM staff
            WHERE id = ?
            AND status = 'Active'
            """,
            (assigned_to,)
        ).fetchone()

        if staff_member is None:
            db.close()

            flash(
                "The selected staff member is not active or does not exist.",
                "danger"
            )

            return redirect(
                url_for(
                    "admin_view_consultation",
                    consultation_id=consultation_id
                )
            )

    updated_at = datetime.now(
        timezone.utc
    ).isoformat()

    db.execute(
        """
        UPDATE consultations
        SET
            assigned_to = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (
            assigned_to,
            updated_at,
            consultation_id
        )
    )

    # Notify assigned staff member
    if staff_member:

        notification_message = (
            f"A consultation request has been assigned to you. "
            f"Request #{consultation_id}: "
            f"{consultation['service'] or 'Consultation'}."
        )

        # Create notification table if it does not exist.
        db.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id INTEGER,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                read INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )

        db.execute(
            """
            INSERT INTO notifications
            (
                staff_id,
                title,
                message,
                created_at
            )
            VALUES (?, ?, ?, ?)
            """,
            (
                staff_member["id"],
                "New Consultation Assigned",
                notification_message,
                updated_at
            )
        )

    db.commit()
    db.close()

    if staff_member:

        flash(
            f"Consultation assigned to "
            f"{staff_member['first_name']} "
            f"{staff_member['last_name']}.",
            "success"
        )

    else:

        flash(
            "Consultation assignment removed.",
            "success"
        )

    return redirect(
        url_for(
            "admin_view_consultation",
            consultation_id=consultation_id
        )
    )


# ============================================================
# ADMIN DELETE CONSULTATION
# ============================================================

@app.route(
    "/admin/consultation/<int:consultation_id>/delete",
    methods=["POST"]
)
@admin_required
def delete_admin_consultation(
    consultation_id
):

    db = get_db()

    consultation = db.execute(
        """
        SELECT *
        FROM consultations
        WHERE id = ?
        """,
        (consultation_id,)
    ).fetchone()

    if consultation is None:
        db.close()

        flash(
            "Consultation request not found.",
            "danger"
        )

        return redirect(
            url_for("admin_consultations")
        )

    db.execute(
        """
        DELETE FROM consultations
        WHERE id = ?
        """,
        (consultation_id,)
    )

    db.commit()
    db.close()

    flash(
        f"Consultation request #{consultation_id} "
        "was deleted successfully.",
        "success"
    )

    return redirect(
        url_for("admin_consultations")
    )

# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    session.pop(
        "admin_logged_in",
        None
    )

    session.pop(
        "admin_email",
        None
    )

    flash(
        "Administrator logged out.",
        "success"
    )

    return redirect(
        url_for("admin_login")
    )


# ============================================================
# MD REGISTRATION
# ============================================================

@app.route(
    "/md/register",
    methods=["GET", "POST"]
)
def md_register():

    db = get_db()

    existing_md = db.execute(
        """
        SELECT id
        FROM md
        LIMIT 1
        """
    ).fetchone()

    db.close()

    if existing_md:

        flash(
            "An MD account has already been registered.",
            "warning"
        )

        return redirect(
            url_for("md_login")
        )

    if request.method == "GET":

        return render_template(
            "md_register.html"
        )

    first_name = request.form.get(
        "first_name",
        ""
    ).strip()

    last_name = request.form.get(
        "last_name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    phone = request.form.get(
        "phone",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    registration_key = request.form.get(
        "registration_key",
        ""
    )

    if not all(
        [
            first_name,
            last_name,
            email,
            phone,
            password,
            confirm_password
        ]
    ):

        flash(
            "Please complete all required fields.",
            "danger"
        )

        return render_template(
            "md_register.html"
        )

    if len(password) < 8:

        flash(
            "Password must contain at least 8 characters.",
            "danger"
        )

        return render_template(
            "md_register.html"
        )

    if password != confirm_password:

        flash(
            "Passwords do not match.",
            "danger"
        )

        return render_template(
            "md_register.html"
        )

    if (
        MD_REGISTRATION_KEY
        and registration_key != MD_REGISTRATION_KEY
    ):

        flash(
            "Invalid MD registration key.",
            "danger"
        )

        return render_template(
            "md_register.html"
        )

    db = get_db()

    try:

        db.execute(
            """
            INSERT INTO md
            (
                first_name,
                last_name,
                email,
                phone,
                password_hash,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'Active', ?)
            """,
            (
                first_name,
                last_name,
                email,
                phone,
                generate_password_hash(
                    password
                ),
                datetime.now(
                    timezone.utc
                ).isoformat()
            )
        )

        db.commit()

    except sqlite3.IntegrityError:

        db.rollback()
        db.close()

        flash(
            "An account with this email already exists.",
            "danger"
        )

        return render_template(
            "md_register.html"
        )

    db.close()

    flash(
        "MD account created successfully.",
        "success"
    )

    return redirect(
        url_for("md_login")
    )


# ============================================================
# MD LOGIN
# ============================================================

@app.route(
    "/md/login",
    methods=["GET", "POST"]
)
def md_login():

    if session.get(
        "md_logged_in"
    ):

        return redirect(
            url_for("md_dashboard")
        )

    if request.method == "GET":

        return render_template(
            "md_login.html"
        )

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    db = get_db()

    md = db.execute(
        """
        SELECT *
        FROM md
        WHERE LOWER(email) = ?
        AND status = 'Active'
        LIMIT 1
        """,
        (
            email,
        )
    ).fetchone()

    if md is None:

        db.close()

        flash(
            "Invalid MD email or password.",
            "danger"
        )

        return render_template(
            "md_login.html"
        )

    if not check_password_hash(
        md["password_hash"],
        password
    ):

        db.close()

        flash(
            "Invalid MD email or password.",
            "danger"
        )

        return render_template(
            "md_login.html"
        )

    db.execute(
        """
        UPDATE md
        SET last_login = ?
        WHERE id = ?
        """,
        (
            datetime.now(
                timezone.utc
            ).isoformat(),
            md["id"]
        )
    )

    db.commit()

    db.close()

    session.clear()

    session["md_logged_in"] = True

    session["md_id"] = md["id"]

    return redirect(
        url_for("md_dashboard")
    )


# ============================================================
# MD DASHBOARD
# ============================================================

@app.route("/md/dashboard")
@md_required
def md_dashboard():

    db = get_db()

    md = db.execute(
        """
        SELECT *
        FROM md
        WHERE id = ?
        """,
        (
            session.get("md_id"),
        )
    ).fetchone()

    total_staff = db.execute(
        """
        SELECT COUNT(*)
        FROM staff
        """
    ).fetchone()[0]

    pending_staff = db.execute(
        """
        SELECT COUNT(*)
        FROM staff
        WHERE status = 'Pending'
        """
    ).fetchone()[0]

    active_staff = db.execute(
        """
        SELECT COUNT(*)
        FROM staff
        WHERE status = 'Active'
        """
    ).fetchone()[0]

    disabled_staff = db.execute(
        """
        SELECT COUNT(*)
        FROM staff
        WHERE status = 'Disabled'
        """
    ).fetchone()[0]

    rejected_staff = db.execute(
        """
        SELECT COUNT(*)
        FROM staff
        WHERE status = 'Rejected'
        """
    ).fetchone()[0]

    total_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        """
    ).fetchone()[0]

    new_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE status = 'New'
        """
    ).fetchone()[0]

    in_progress_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE status = 'In Progress'
        """
    ).fetchone()[0]

    closed_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE status = 'Closed'
        """
    ).fetchone()[0]

    unassigned_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE assigned_staff_id IS NULL
        """
    ).fetchone()[0]

    assigned_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE assigned_staff_id IS NOT NULL
        """
    ).fetchone()[0]

    recent_staff = db.execute(
        """
        SELECT *
        FROM staff
        ORDER BY id DESC
        LIMIT 10
        """
    ).fetchall()

    recent_consultations = db.execute(
        """
        SELECT
            consultations.*,

            staff.first_name
                AS assigned_first_name,

            staff.last_name
                AS assigned_last_name,

            staff.staff_id
                AS assigned_staff_code

        FROM consultations

        LEFT JOIN staff
            ON consultations.assigned_staff_id = staff.id

        ORDER BY consultations.id DESC

        LIMIT 10
        """
    ).fetchall()

    db.close()

    return render_template(
        "md_dashboard.html",

        md=md,

        total_staff=total_staff,

        pending_staff=pending_staff,

        active_staff=active_staff,

        disabled_staff=disabled_staff,

        rejected_staff=rejected_staff,

        total_consultations=
            total_consultations,

        consultations=
            total_consultations,

        new_consultations=
            new_consultations,

        in_progress_consultations=
            in_progress_consultations,

        closed_consultations=
            closed_consultations,

        unassigned_consultations=
            unassigned_consultations,

        assigned_consultations=
            assigned_consultations,

        recent_staff=
            recent_staff,

        recent_consultations=
            recent_consultations
    )


# ============================================================
# MD STAFF
# ============================================================

@app.route("/md/staff")
@md_required
def md_staff():

    db = get_db()

    staff = db.execute(
        """
        SELECT *
        FROM staff
        ORDER BY id DESC
        """
    ).fetchall()

    db.close()

    return render_template(
        "md_staff.html",
        staff=staff
    )


# ============================================================
# MD VIEW STAFF
# ============================================================

@app.route(
    "/md/staff/<int:staff_db_id>"
)
@md_required
def md_view_staff(
    staff_db_id
):

    db = get_db()

    staff = db.execute(
        """
        SELECT *
        FROM staff
        WHERE id = ?
        """,
        (
            staff_db_id,
        )
    ).fetchone()

    db.close()

    if staff is None:

        abort(404)

    return render_template(
        "md_view_staff.html",
        staff=staff
    )


# ============================================================
# MD STAFF ACTION
# ============================================================

@app.route(
    "/md/staff/<int:staff_db_id>/<action>",
    methods=["POST"]
)
@md_required
def md_staff_action(
    staff_db_id,
    action
):

    allowed_actions = (
        "approve",
        "reject",
        "disable",
        "activate"
    )

    if action not in allowed_actions:

        abort(400)

    db = get_db()

    staff = db.execute(
        """
        SELECT *
        FROM staff
        WHERE id = ?
        """,
        (
            staff_db_id,
        )
    ).fetchone()

    if staff is None:

        db.close()

        abort(404)

    if action == "approve":

        db.execute(
            """
            UPDATE staff
            SET status = 'Active',
                approved_at = ?
            WHERE id = ?
            """,
            (
                datetime.now(
                    timezone.utc
                ).isoformat(),
                staff_db_id
            )
        )

        message = (
            f"{staff['first_name']} "
            f"{staff['last_name']} "
            "has been approved."
        )

        category = "success"

        send_approval_email(
            staff["first_name"],
            staff["staff_id"],
            staff["email"]
        )

    elif action == "reject":

        db.execute(
            """
            UPDATE staff
            SET status = 'Rejected'
            WHERE id = ?
            """,
            (
                staff_db_id,
            )
        )

        message = (
            f"{staff['first_name']} "
            f"{staff['last_name']} "
            "has been rejected."
        )

        category = "warning"

    elif action == "disable":

        db.execute(
            """
            UPDATE staff
            SET status = 'Disabled'
            WHERE id = ?
            """,
            (
                staff_db_id,
            )
        )

        message = (
            "Staff account has been disabled."
        )

        category = "warning"

    else:

        db.execute(
            """
            UPDATE staff
            SET status = 'Active'
            WHERE id = ?
            """,
            (
                staff_db_id,
            )
        )

        message = (
            "Staff account has been activated."
        )

        category = "success"

    db.commit()

    db.close()

    log_activity(
        "MD",
        f"Staff {action}",
        f"Staff database ID: {staff_db_id}"
    )

    flash(
        message,
        category
    )

    return redirect(
        url_for("md_staff")
    )


# ============================================================
# MD CONSULTATIONS
# ============================================================

@app.route("/md/consultations")
@md_required
def md_consultations():

    db = get_db()

    consultations = db.execute(
        """
        SELECT
            consultations.*,

            staff.first_name
                AS assigned_first_name,

            staff.last_name
                AS assigned_last_name,

            staff.staff_id
                AS assigned_staff_code,

            staff.department
                AS assigned_department,

            staff.position
                AS assigned_position,

            staff.email
                AS assigned_email

        FROM consultations

        LEFT JOIN staff
            ON consultations.assigned_staff_id = staff.id

        ORDER BY consultations.id DESC
        """
    ).fetchall()

    staff = db.execute(
        """
        SELECT
            id,
            staff_id,
            first_name,
            last_name,
            department,
            position,
            email

        FROM staff

        WHERE status = 'Active'

        ORDER BY first_name ASC,
                 last_name ASC
        """
    ).fetchall()

    total_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        """
    ).fetchone()[0]

    new_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE status = 'New'
        """
    ).fetchone()[0]

    in_progress_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE status = 'In Progress'
        """
    ).fetchone()[0]

    closed_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE status = 'Closed'
        """
    ).fetchone()[0]

    unassigned_consultations = db.execute(
        """
        SELECT COUNT(*)
        FROM consultations
        WHERE assigned_staff_id IS NULL
        """
    ).fetchone()[0]

    db.close()

    return render_template(
        "md_consultations.html",

        consultations=consultations,

        staff=staff,

        total_consultations=
            total_consultations,

        new_consultations=
            new_consultations,

        in_progress_consultations=
            in_progress_consultations,

        closed_consultations=
            closed_consultations,

        unassigned_consultations=
            unassigned_consultations
    )


# ============================================================
# MD CONSULTATION DETAIL
# ============================================================

@app.route(
    "/md/consultation/<int:consultation_id>"
)
@md_required
def md_view_consultation(
    consultation_id
):

    db = get_db()

    consultation = db.execute(
        """
        SELECT
            consultations.*,

            staff.first_name
                AS assigned_first_name,

            staff.last_name
                AS assigned_last_name,

            staff.staff_id
                AS assigned_staff_code,

            staff.department
                AS assigned_department,

            staff.position
                AS assigned_position,

            staff.email
                AS assigned_email

        FROM consultations

        LEFT JOIN staff
            ON consultations.assigned_staff_id = staff.id

        WHERE consultations.id = ?
        """,
        (
            consultation_id,
        )
    ).fetchone()

    staff = db.execute(
        """
        SELECT
            id,
            staff_id,
            first_name,
            last_name,
            department,
            position,
            email

        FROM staff

        WHERE status = 'Active'

        ORDER BY first_name ASC,
                 last_name ASC
        """
    ).fetchall()

    db.close()

    if consultation is None:

        abort(404)

    return render_template(
        "md_consultation_detail.html",

        consultation=consultation,

        staff=staff
    )


# ============================================================
# MD ASSIGN CONSULTATION
# ============================================================

@app.route(
    "/md/consultation/<int:consultation_id>/assign",
    methods=["POST"]
)
@md_required
def md_assign_consultation(
    consultation_id
):

    selected_staff_id = request.form.get(
        "staff_id",
        ""
    ).strip()

    if not selected_staff_id:

        flash(
            "Please select a staff member.",
            "warning"
        )

        return redirect(
            request.referrer
            or url_for(
                "md_consultations"
            )
        )

    try:

        selected_staff_db_id = int(
            selected_staff_id
        )

    except ValueError:

        flash(
            "Invalid staff selection.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "md_consultations"
            )
        )

    db = get_db()

    consultation = db.execute(
        """
        SELECT *
        FROM consultations
        WHERE id = ?
        """,
        (
            consultation_id,
        )
    ).fetchone()

    if consultation is None:

        db.close()

        abort(404)

    staff = db.execute(
        """
        SELECT *
        FROM staff
        WHERE id = ?
        AND status = 'Active'
        LIMIT 1
        """,
        (
            selected_staff_db_id,
        )
    ).fetchone()

    if staff is None:

        db.close()

        flash(
            "Selected staff member is not active.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "md_consultations"
            )
        )

    db.execute(
        """
        UPDATE consultations

        SET assigned_staff_id = ?

        WHERE id = ?
        """,
        (
            staff["id"],
            consultation_id
        )
    )

    if consultation["status"] == "New":

        db.execute(
            """
            UPDATE consultations

            SET status = 'In Progress'

            WHERE id = ?
            """,
            (
                consultation_id,
            )
        )

    db.commit()

    verification = db.execute(
        """
        SELECT
            assigned_staff_id,
            status
        FROM consultations
        WHERE id = ?
        """,
        (
            consultation_id,
        )
    ).fetchone()

    db.close()

    if verification is None:

        flash(
            "Assignment verification failed.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "md_consultations"
            )
        )

    if (
        verification["assigned_staff_id"]
        != staff["id"]
    ):

        flash(
            "The consultation could not be assigned.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "md_consultations"
            )
        )

    email_sent = send_assignment_email(
        staff,
        consultation
    )

    log_activity(
        "MD",
        "Consultation Assigned",
        (
            f"Consultation #{consultation_id} "
            f"assigned to {staff['staff_id']}"
        )
    )

    if email_sent:

        flash(
            f"Consultation #{consultation_id} "
            f"assigned successfully to "
            f"{staff['first_name']} "
            f"{staff['last_name']}. "
            "Notification email sent.",
            "success"
        )

    else:

        flash(
            f"Consultation #{consultation_id} "
            f"assigned successfully to "
            f"{staff['first_name']} "
            f"{staff['last_name']}, "
            "but notification email failed.",
            "warning"
        )

    return redirect(
        request.referrer
        or url_for(
            "md_consultations"
        )
    )


# ============================================================
# MD UNASSIGN CONSULTATION
# ============================================================

@app.route(
    "/md/consultation/<int:consultation_id>/unassign",
    methods=["POST"]
)
@md_required
def md_unassign_consultation(
    consultation_id
):

    db = get_db()

    consultation = db.execute(
        """
        SELECT id
        FROM consultations
        WHERE id = ?
        """,
        (
            consultation_id,
        )
    ).fetchone()

    if consultation is None:

        db.close()

        abort(404)

    db.execute(
        """
        UPDATE consultations

        SET assigned_staff_id = NULL

        WHERE id = ?
        """,
        (
            consultation_id,
        )
    )

    db.commit()

    db.close()

    log_activity(
        "MD",
        "Consultation Unassigned",
        (
            f"Consultation #{consultation_id} "
            "unassigned"
        )
    )

    flash(
        "Consultation has been unassigned.",
        "success"
    )

    return redirect(
        request.referrer
        or url_for(
            "md_consultations"
        )
    )


# ============================================================
# MD UPDATE CONSULTATION STATUS
# ============================================================

@app.route(
    "/md/consultation/<int:consultation_id>/status",
    methods=["POST"]
)
@md_required
def md_update_consultation_status(
    consultation_id
):

    status = request.form.get(
        "status",
        "New"
    ).strip()

    allowed_statuses = (
        "New",
        "In Progress",
        "Closed"
    )

    if status not in allowed_statuses:

        flash(
            "Invalid consultation status.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for(
                "md_consultations"
            )
        )

    db = get_db()

    consultation = db.execute(
        """
        SELECT id
        FROM consultations
        WHERE id = ?
        """,
        (
            consultation_id,
        )
    ).fetchone()

    if consultation is None:

        db.close()

        abort(404)

    db.execute(
        """
        UPDATE consultations

        SET status = ?

        WHERE id = ?
        """,
        (
            status,
            consultation_id
        )
    )

    db.commit()

    db.close()

    log_activity(
        "MD",
        "Consultation Status Updated",
        (
            f"Consultation #{consultation_id}: "
            f"{status}"
        )
    )

    flash(
        "Consultation status updated.",
        "success"
    )

    return redirect(
        request.referrer
        or url_for(
            "md_consultations"
        )
    )


# ============================================================
# MD LOGOUT
# ============================================================

@app.route("/md/logout")
def md_logout():

    session.pop(
        "md_logged_in",
        None
    )

    session.pop(
        "md_id",
        None
    )

    flash(
        "MD logged out.",
        "success"
    )

    return redirect(
        url_for("md_login")
    )


# ============================================================
# PUBLIC CONSULTATION API
# ============================================================

@app.route(
    "/api/consultation",
    methods=["POST"]
)
def create_consultation():

    data = (
        request.get_json(
            silent=True
        )
        or request.form
    )

    name = str(
        data.get(
            "name",
            ""
        )
    ).strip()

    email = str(
        data.get(
            "email",
            ""
        )
    ).strip()

    phone = str(
        data.get(
            "phone",
            ""
        )
    ).strip()

    company = str(
        data.get(
            "company",
            ""
        )
    ).strip()

    service = str(
        data.get(
            "service",
            ""
        )
    ).strip()

    message = str(
        data.get(
            "message",
            ""
        )
    ).strip()

    if not name or not service:

        return jsonify(
            success=False,
            message=(
                "Name and service are required."
            )
        ), 400

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    db = get_db()

    cursor = db.execute(
        """
        INSERT INTO consultations
        (
            name,
            email,
            phone,
            company,
            service,
            message,
            status,
            created_at,
            assigned_staff_id
        )
        VALUES (?, ?, ?, ?, ?, ?, 'New', ?, NULL)
        """,
        (
            name,
            email,
            phone,
            company,
            service,
            message,
            created_at
        )
    )

    consultation_id = cursor.lastrowid

    db.commit()

    db.close()

    email_sent = send_consultation_notification(
        consultation_id,
        name,
        email,
        phone,
        company,
        service,
        message
    )

    log_activity(
        "Public Website",
        "Consultation Created",
        (
            f"Consultation #{consultation_id}"
        )
    )

    return jsonify(
        success=True,
        message=(
            "Consultation request received."
        ),
        consultation_id=consultation_id,
        email_sent=email_sent
    )


# ============================================================
# ERROR HANDLER - 404
# ============================================================

@app.errorhandler(404)
def page_not_found(error):

    try:

        return render_template(
            "404.html"
        ), 404

    except Exception:

        return (
            "Page not found.",
            404
        )


# ============================================================
# ERROR HANDLER - 500
# ============================================================

@app.errorhandler(500)
def internal_server_error(error):

    try:

        return render_template(
            "500.html"
        ), 500

    except Exception:

        return (
            "Internal server error.",
            500
        )


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":

    init_db()

    migrate_database()

    print()
    print("=" * 70)
    print("NOVERA ENERGY & TECHNOLOGIES PORTAL")
    print("=" * 70)

    print()

    print(
        "Project Directory:"
    )

    print(
        PROJECT_DIR
    )

    print()

    print(
        "Backend Directory:"
    )

    print(
        BASE_DIR
    )

    print()

    print(
        "Templates Directory:"
    )

    print(
        TEMPLATES_DIR
    )

    print()

    print(
        "Assets Directory:"
    )

    print(
        ASSETS_DIR
    )

    print()

    print(
        "Database:"
    )

    print(
        DATABASE_PATH
    )

    print()

    print(
        "Logo:"
    )

    print(
        LOGO_PATH
    )

    print()

    print(
        "Logo Exists:"
    )

    print(
        LOGO_PATH.exists()
    )

    print()

    print(
        "Consultation Email:"
    )

    print(
        CONSULTATION_EMAIL
    )

    print()

    print(
        "Main Portal:"
    )

    print(
        "http://127.0.0.1:5000/"
    )

    print()

    print(
        "Staff Registration:"
    )

    print(
        "http://127.0.0.1:5000/staff/register"
    )

    print()

    print(
        "Staff Login:"
    )

    print(
        "http://127.0.0.1:5000/staff/login"
    )

    print()

    print(
        "Staff Dashboard:"
    )

    print(
        "http://127.0.0.1:5000/staff/dashboard"
    )

    print()

    print(
        "Staff Consultations:"
    )

    print(
        "http://127.0.0.1:5000/staff/consultations"
    )

    print()

    print(
        "MD Registration:"
    )

    print(
        "http://127.0.0.1:5000/md/register"
    )

    print()

    print(
        "MD Login:"
    )

    print(
        "http://127.0.0.1:5000/md/login"
    )

    print()

    print(
        "MD Dashboard:"
    )

    print(
        "http://127.0.0.1:5000/md/dashboard"
    )

    print()

    print(
        "MD Consultations:"
    )

    print(
        "http://127.0.0.1:5000/md/consultations"
    )

    print()

    print(
        "Admin Login:"
    )

    print(
        "http://127.0.0.1:5000/admin/login"
    )

    print()

    print(
        "Admin Dashboard:"
    )

    print(
        "http://127.0.0.1:5000/admin/dashboard"
    )

    print()

    print(
        "Admin Consultations:"
    )

    print(
        "http://127.0.0.1:5000/admin/consultations"
    )

    print()

    print(
        "Logo URL:"
    )

    print(
        "http://127.0.0.1:5000/logo.jpg"
    )

    print()

    print("=" * 70)

    app.run(
        host="0.0.0.0",

        port=int(
            os.getenv(
                "PORT",
                "5000"
            )
        ),

        debug=(
            os.getenv(
                "FLASK_DEBUG",
                "True"
            ).lower() == "true"
        )
    )