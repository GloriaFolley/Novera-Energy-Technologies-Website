from pathlib import Path
from functools import wraps
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
import os
import smtplib
import sqlite3
import secrets
import hashlib

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import (
    check_password_hash,
    generate_password_hash,
)
from werkzeug.utils import secure_filename


# ============================================================
# PATH CONFIGURATION
# ============================================================

BACKEND_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BACKEND_DIR.parent
PROJECT_DIR = ASSETS_DIR.parent

TEMPLATES_DIR = BACKEND_DIR / "templates"
DATABASE_PATH = BACKEND_DIR / "novera.db"

LOGO_PATH = ASSETS_DIR / "logo.jpg"
INDEX_FILE = PROJECT_DIR / "index.html"

# Private staff profile photo storage.
PROFILE_PHOTO_DIR = BACKEND_DIR / "profile_photos"
PROFILE_PHOTO_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_PROFILE_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
MAX_PROFILE_PHOTO_SIZE = 5 * 1024 * 1024

PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
RESET_TOKEN_MINUTES = 30

DATABASE_PATH.parent.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# ENVIRONMENT
# ============================================================

BACKEND_ENV_FILE = BACKEND_DIR / ".env"
PROJECT_ENV_FILE = PROJECT_DIR / ".env"

if BACKEND_ENV_FILE.exists():
    load_dotenv(BACKEND_ENV_FILE)
elif PROJECT_ENV_FILE.exists():
    load_dotenv(PROJECT_ENV_FILE)
else:
    load_dotenv()


# ============================================================
# COMPANY CONFIGURATION
# ============================================================

COMPANY_NAME = os.getenv(
    "COMPANY_NAME",
    "Novera Energy & Technologies"
).strip()

COMPANY_EMAIL = os.getenv(
    "COMPANY_EMAIL",
    "noveratech001@gmail.com"
).strip()

COMPANY_TAGLINE = "Light · Motion · Intelligence"


# ============================================================
# ADMIN CONFIGURATION
# ============================================================

ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL",
    "admin@novera.com"
).strip().lower()

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "ChangeThisPassword123!"
)

STAFF_EMAIL_DOMAIN = os.getenv(
    "STAFF_EMAIL_DOMAIN",
    ""
).strip().lower()


# ============================================================
# FLASK
# ============================================================

app = Flask(
    __name__,
    template_folder=str(TEMPLATES_DIR)
)

app.config.update(
    SECRET_KEY=os.getenv(
        "SECRET_KEY",
        "CHANGE-ME-IN-PRODUCTION"
    ),

    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",

    SESSION_COOKIE_SECURE=(
        os.getenv(
            "SESSION_COOKIE_SECURE",
            "false"
        ).lower() == "true"
    ),

    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
)


# ============================================================
# CONSTANTS
# ============================================================

STAFF_STATUSES = (
    "Pending",
    "Active",
    "Rejected",
    "Disabled",
)

CONSULTATION_STATUSES = (
    "New",
    "In Progress",
    "Closed",
)

TRAINING_APPLICATION_STATUSES = (
    "New",
    "Under Review",
    "Accepted",
    "Rejected",
)


# ============================================================
# TIME
# ============================================================

def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# DATABASE
# ============================================================

def get_db():
    """
    Open the Novera SQLite database.
    """

    db = sqlite3.connect(
        str(DATABASE_PATH),
        timeout=30
    )

    db.row_factory = sqlite3.Row

    db.execute(
        "PRAGMA foreign_keys = ON"
    )

    return db


def close_db(db):
    if db is not None:
        db.close()


def table_columns(db, table_name):
    return {
        row["name"]
        for row in db.execute(
            f"PRAGMA table_info({table_name})"
        ).fetchall()
    }


def ensure_column(
    db,
    table_name,
    column_name,
    definition
):
    columns = table_columns(
        db,
        table_name
    )

    if column_name not in columns:
        db.execute(
            f"""
            ALTER TABLE {table_name}
            ADD COLUMN {column_name} {definition}
            """
        )


# ============================================================
# TRAINING APPLICATION ID
# ============================================================

def generate_training_application_id(db):
    """
    Generate a unique training application reference.

    Example:
        NVR-TRN-582341
    """

    while True:

        application_id = (
            "NVR-TRN-"
            + str(
                secrets.randbelow(
                    900000
                ) + 100000
            )
        )

        exists = db.execute(
            """
            SELECT id
            FROM training_applications
            WHERE application_id = ?
            LIMIT 1
            """,
            (application_id,)
        ).fetchone()

        if not exists:
            return application_id


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_database():

    db = get_db()

    try:

        # ====================================================
        # ADMINS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                first_name TEXT,
                last_name TEXT,
                status TEXT DEFAULT 'Active',
                created_at TEXT,
                last_login TEXT
            )
        """)


        # ====================================================
        # STAFF
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS staff (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                staff_id TEXT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                email TEXT UNIQUE,
                phone TEXT,
                department TEXT,
                position TEXT,
                password_hash TEXT NOT NULL,
                status TEXT DEFAULT 'Pending',
                created_at TEXT,
                approved_at TEXT,
                last_login TEXT,
                profile_photo TEXT
            )
        """)


        # ====================================================
        # CONSULTATIONS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS consultations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                name TEXT NOT NULL,
                email TEXT,
                phone TEXT,
                company TEXT,
                service TEXT NOT NULL,
                message TEXT,

                language TEXT DEFAULT 'en',

                status TEXT DEFAULT 'New',

                assigned_staff_id INTEGER,
                assigned_to INTEGER,

                assigned_by INTEGER,
                assigned_at TEXT,

                created_at TEXT,
                updated_at TEXT,

                email_sent INTEGER DEFAULT 0,

                FOREIGN KEY (assigned_staff_id)
                    REFERENCES staff(id)
                    ON DELETE SET NULL,

                FOREIGN KEY (assigned_to)
                    REFERENCES staff(id)
                    ON DELETE SET NULL,

                FOREIGN KEY (assigned_by)
                    REFERENCES admins(id)
                    ON DELETE SET NULL
            )
        """)


        # ====================================================
        # TRAINING APPLICATIONS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS training_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                application_id TEXT UNIQUE NOT NULL,

                full_name TEXT NOT NULL,

                email TEXT NOT NULL,

                phone TEXT NOT NULL,

                program TEXT NOT NULL,

                education TEXT,

                company TEXT,

                experience TEXT,

                motivation TEXT NOT NULL,

                message TEXT,

                status TEXT DEFAULT 'New',

                created_at TEXT,

                updated_at TEXT,

                email_sent INTEGER DEFAULT 0
            )
        """)


        # ====================================================
        # NOTIFICATIONS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                staff_id INTEGER NOT NULL,

                title TEXT NOT NULL,
                message TEXT NOT NULL,

                is_read INTEGER DEFAULT 0,

                created_at TEXT,

                FOREIGN KEY (staff_id)
                    REFERENCES staff(id)
                    ON DELETE CASCADE
            )
        """)


        # ====================================================
        # ACTIVITY LOGS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,

                actor_type TEXT,
                actor_id INTEGER,

                action TEXT NOT NULL,
                description TEXT,

                created_at TEXT
            )
        """)


        # ====================================================
        # PASSWORD RESET TOKENS
        # ====================================================

        db.execute("""
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                account_type TEXT NOT NULL,
                account_id INTEGER NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                expires_at TEXT NOT NULL,
                used_at TEXT,
                created_at TEXT NOT NULL
            )
        """)


        # ====================================================
        # SAFE MIGRATIONS
        # ====================================================

        ensure_column(
            db,
            "admins",
            "last_login",
            "TEXT"
        )

        ensure_column(
            db,
            "staff",
            "email",
            "TEXT"
        )

        ensure_column(
            db,
            "staff",
            "phone",
            "TEXT"
        )

        ensure_column(
            db,
            "staff",
            "department",
            "TEXT"
        )

        ensure_column(
            db,
            "staff",
            "position",
            "TEXT"
        )

        ensure_column(
            db,
            "staff",
            "approved_at",
            "TEXT"
        )

        ensure_column(
            db,
            "staff",
            "last_login",
            "TEXT"
        )

        ensure_column(
            db,
            "staff",
            "profile_photo",
            "TEXT"
        )

        ensure_column(
            db,
            "consultations",
            "company",
            "TEXT"
        )

        ensure_column(
            db,
            "consultations",
            "language",
            "TEXT"
        )

        ensure_column(
            db,
            "consultations",
            "status",
            "TEXT DEFAULT 'New'"
        )

        ensure_column(
            db,
            "consultations",
            "assigned_staff_id",
            "INTEGER"
        )

        ensure_column(
            db,
            "consultations",
            "assigned_to",
            "INTEGER"
        )

        ensure_column(
            db,
            "consultations",
            "assigned_by",
            "INTEGER"
        )

        ensure_column(
            db,
            "consultations",
            "assigned_at",
            "TEXT"
        )

        ensure_column(
            db,
            "consultations",
            "updated_at",
            "TEXT"
        )

        ensure_column(
            db,
            "consultations",
            "email_sent",
            "INTEGER DEFAULT 0"
        )


        # ====================================================
        # TRAINING APPLICATION MIGRATIONS
        # ====================================================

        ensure_column(
            db,
            "training_applications",
            "application_id",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "full_name",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "email",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "phone",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "program",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "education",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "company",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "experience",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "motivation",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "message",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "status",
            "TEXT DEFAULT 'New'"
        )

        ensure_column(
            db,
            "training_applications",
            "created_at",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "updated_at",
            "TEXT"
        )

        ensure_column(
            db,
            "training_applications",
            "email_sent",
            "INTEGER DEFAULT 0"
        )


        # ====================================================
        # DEFAULT VALUES FOR EXISTING CONSULTATIONS
        # ====================================================

        db.execute("""
            UPDATE consultations
            SET status = 'New'
            WHERE status IS NULL
               OR TRIM(status) = ''
        """)

        db.execute("""
            UPDATE consultations
            SET language = 'en'
            WHERE language IS NULL
               OR TRIM(language) = ''
        """)


        # ====================================================
        # DEFAULT VALUES FOR TRAINING APPLICATIONS
        # ====================================================

        db.execute("""
            UPDATE training_applications
            SET status = 'New'
            WHERE status IS NULL
               OR TRIM(status) = ''
        """)

        db.execute("""
            UPDATE training_applications
            SET created_at = ?
            WHERE created_at IS NULL
               OR TRIM(created_at) = ''
        """, (utc_now(),))

        db.execute("""
            UPDATE training_applications
            SET updated_at = created_at
            WHERE updated_at IS NULL
               OR TRIM(updated_at) = ''
        """)


        # ====================================================
        # CREATE MISSING TRAINING APPLICATION IDs
        # ====================================================

        existing_training_rows = db.execute(
            """
            SELECT id
            FROM training_applications
            WHERE application_id IS NULL
               OR TRIM(application_id) = ''
            ORDER BY id ASC
            """
        ).fetchall()

        for row in existing_training_rows:

            application_id = generate_training_application_id(
                db
            )

            db.execute(
                """
                UPDATE training_applications
                SET application_id = ?
                WHERE id = ?
                """,
                (
                    application_id,
                    row["id"]
                )
            )


        # ====================================================
        # CREATE ADMIN FROM .ENV
        # ====================================================

        existing_admin = db.execute(
            """
            SELECT id
            FROM admins
            WHERE LOWER(email) = LOWER(?)
            LIMIT 1
            """,
            (ADMIN_EMAIL,)
        ).fetchone()


        if existing_admin is None:

            db.execute(
                """
                INSERT INTO admins (
                    email,
                    password_hash,
                    first_name,
                    last_name,
                    status,
                    created_at
                )
                VALUES (?, ?, ?, ?, 'Active', ?)
                """,
                (
                    ADMIN_EMAIL,
                    generate_password_hash(
                        ADMIN_PASSWORD
                    ),
                    "System",
                    "Administrator",
                    utc_now()
                )
            )

            print()
            print("=" * 65)
            print("NOVERA ADMIN ACCOUNT CREATED")
            print("=" * 65)
            print(f"Email    : {ADMIN_EMAIL}")
            print("Password : Loaded from .env")
            print("Status   : Active")
            print("=" * 65)
            print()

        else:

            print()
            print("=" * 65)
            print("NOVERA ADMIN ACCOUNT ALREADY EXISTS")
            print("=" * 65)
            print(f"Email    : {ADMIN_EMAIL}")
            print("Password : Existing password retained")
            print("Status   : Active")
            print("=" * 65)
            print()


        db.commit()

        print(
            f"[DATABASE] Ready: {DATABASE_PATH}"
        )

    except Exception as error:

        db.rollback()

        print()
        print("[DATABASE INITIALIZATION ERROR]")
        print(error)
        print()

        raise

    finally:
        close_db(db)


# ============================================================
# ACTIVITY LOG
# ============================================================

def log_activity(
    actor_type,
    actor_id,
    action,
    description=""
):

    db = get_db()

    try:

        db.execute(
            """
            INSERT INTO activity_logs (
                actor_type,
                actor_id,
                action,
                description,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                actor_type,
                actor_id,
                action,
                description,
                utc_now()
            )
        )

        db.commit()

    finally:
        close_db(db)


# ============================================================
# NOTIFICATIONS
# ============================================================

def create_notification(
    staff_id,
    title,
    message
):

    db = get_db()

    try:

        db.execute(
            """
            INSERT INTO notifications (
                staff_id,
                title,
                message,
                is_read,
                created_at
            )
            VALUES (?, ?, ?, 0, ?)
            """,
            (
                staff_id,
                title,
                message,
                utc_now()
            )
        )

        db.commit()

    finally:
        close_db(db)


# ============================================================
# EMAIL
# ============================================================

def send_email(
    recipient,
    subject,
    body,
    reply_to=None
):

    smtp_host = os.getenv(
        "MAIL_SERVER",
        ""
    ).strip()

    smtp_port = int(
        os.getenv(
            "MAIL_PORT",
            "587"
        )
    )

    smtp_username = os.getenv(
        "MAIL_USERNAME",
        ""
    ).strip()

    smtp_password = os.getenv(
        "MAIL_PASSWORD",
        ""
    )

    use_tls = (
        os.getenv(
            "MAIL_USE_TLS",
            "true"
        ).lower() == "true"
    )

    if not all([
        smtp_host,
        smtp_username,
        smtp_password,
        recipient,
    ]):
        return False, "SMTP is not configured."

    msg = EmailMessage()

    msg["Subject"] = subject
    msg["From"] = smtp_username
    msg["To"] = recipient

    if reply_to:
        msg["Reply-To"] = reply_to

    msg.set_content(body)

    try:

        with smtplib.SMTP(
            smtp_host,
            smtp_port,
            timeout=20
        ) as smtp:

            if use_tls:
                smtp.starttls()

            smtp.login(
                smtp_username,
                smtp_password
            )

            smtp.send_message(msg)

        return True, None

    except Exception as error:

        app.logger.exception(
            "Email sending failed"
        )

        return False, str(error)


def send_consultation_email(
    consultation
):

    body = f"""
{COMPANY_NAME}
New Consultation Request

Consultation ID:
#{consultation["id"]}

Customer:
{consultation["name"]}

Email:
{consultation["email"] or "Not provided"}

Phone:
{consultation["phone"] or "Not provided"}

Company:
{consultation["company"] or "Not provided"}

Service:
{consultation["service"]}

Language:
{consultation["language"] or "en"}

Message:
{consultation["message"] or "No additional details provided."}

Received:
{consultation["created_at"]}
"""

    return send_email(
        COMPANY_EMAIL,
        f"New Consultation Request - {consultation['service']}",
        body,
        consultation["email"] or None
    )


def send_assignment_email(
    staff,
    consultation
):

    if not staff["email"]:
        return False, "Staff member has no email address."

    body = f"""
{COMPANY_NAME}

A consultation has been assigned to you.

Consultation ID:
#{consultation["id"]}

Customer:
{consultation["name"]}

Phone:
{consultation["phone"] or "Not provided"}

Email:
{consultation["email"] or "Not provided"}

Service:
{consultation["service"]}

Message:
{consultation["message"] or "No additional details provided."}
"""

    return send_email(
        staff["email"],
        f"Consultation #{consultation['id']} Assigned",
        body,
        consultation["email"] or None
    )


# ============================================================
# TRAINING APPLICATION EMAIL
# ============================================================

def send_training_application_email(
    application
):

    body = f"""
{COMPANY_NAME}
New Training Program Application

Application ID:
{application["application_id"]}

Applicant:
{application["full_name"]}

Email:
{application["email"]}

Phone:
{application["phone"]}

Training Program:
{application["program"]}

Educational / Professional Background:
{application["education"] or "Not provided"}

Company / Organization:
{application["company"] or "Not provided"}

Previous Experience:
{application["experience"] or "Not provided"}

Why the applicant wants to join:
{application["motivation"]}

Additional Information:
{application["message"] or "Not provided"}

Status:
{application["status"]}

Submitted:
{application["created_at"]}
"""

    return send_email(
        COMPANY_EMAIL,
        (
            "New Training Application - "
            f"{application['application_id']}"
        ),
        body,
        application["email"]
    )


# ============================================================
# STAFF EMAIL
# ============================================================

def generate_staff_email(
    first_name,
    last_name,
    staff_id
):

    if not STAFF_EMAIL_DOMAIN:
        return None

    first = "".join(
        character
        for character in first_name.lower()
        if character.isalnum()
    )

    last = "".join(
        character
        for character in last_name.lower()
        if character.isalnum()
    )

    if not first or not last:
        return None

    return (
        f"{first}.{last}.{staff_id.lower()}"
        f"@{STAFF_EMAIL_DOMAIN}"
    )


# ============================================================
# STAFF ID
# ============================================================

def generate_staff_id(db):

    while True:

        staff_id = (
            "NVR-"
            + str(
                secrets.randbelow(
                    900000
                ) + 100000
            )
        )

        exists = db.execute(
            """
            SELECT id
            FROM staff
            WHERE staff_id = ?
            """,
            (staff_id,)
        ).fetchone()

        if not exists:
            return staff_id


# ============================================================
# CONTEXT
# ============================================================

@app.context_processor
def inject_company_context():

    return {
        "company_name": COMPANY_NAME,
        "company_tagline": COMPANY_TAGLINE,
        "logo_url": url_for("logo"),
    }


# ============================================================
# ADMIN AUTHENTICATION
# ============================================================

def current_admin():

    admin_id = session.get(
        "admin_id"
    )

    if not admin_id:
        return None

    db = get_db()

    try:

        admin = db.execute(
            """
            SELECT *
            FROM admins
            WHERE id = ?
              AND status = 'Active'
            LIMIT 1
            """,
            (admin_id,)
        ).fetchone()

        return admin

    finally:
        close_db(db)


def admin_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        admin = current_admin()

        if not admin:

            flash(
                "Please log in as administrator.",
                "danger"
            )

            return redirect(
                url_for("admin_login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


# ============================================================
# STAFF AUTHENTICATION
# ============================================================

def current_staff():

    staff_db_id = session.get(
        "staff_db_id"
    )

    if not staff_db_id:
        return None

    db = get_db()

    try:

        staff = db.execute(
            """
            SELECT *
            FROM staff
            WHERE id = ?
            LIMIT 1
            """,
            (staff_db_id,)
        ).fetchone()

        return staff

    finally:
        close_db(db)


def staff_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        staff = current_staff()

        if not staff:

            flash(
                "Please log in as staff.",
                "danger"
            )

            return redirect(
                url_for("staff_login")
            )

        if staff["status"] != "Active":

            session.clear()

            flash(
                "Your staff account is not active.",
                "danger"
            )

            return redirect(
                url_for("staff_login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


# ============================================================
# MD AUTHENTICATION
# ============================================================

def current_md():

    md_id = session.get(
        "md_id"
    )

    if not md_id:
        return None

    db = get_db()

    try:

        admin = db.execute(
            """
            SELECT *
            FROM admins
            WHERE id = ?
              AND status = 'Active'
            LIMIT 1
            """,
            (md_id,)
        ).fetchone()

        return admin

    finally:
        close_db(db)


def md_required(view):

    @wraps(view)
    def wrapped(*args, **kwargs):

        md = current_md()

        if not md:

            flash(
                "Please log in as management.",
                "danger"
            )

            return redirect(
                url_for("md_login")
            )

        return view(
            *args,
            **kwargs
        )

    return wrapped


# ============================================================
# PUBLIC WEBSITE
# ============================================================

@app.route("/")
def home():

    if not INDEX_FILE.exists():
        return (
            "Novera website index.html not found.",
            404
        )

    return send_file(
        INDEX_FILE
    )


@app.route("/index")
def index():

    return home()


@app.route("/assets/<path:filename>")
def assets(filename):

    return send_from_directory(
        ASSETS_DIR,
        filename
    )


@app.route("/logo")
def logo():

    if not LOGO_PATH.exists():
        abort(404)

    return send_file(
        LOGO_PATH,
        mimetype="image/jpeg"
    )


@app.route("/company-profile")
def company_profile():

    pdf_path = (
        ASSETS_DIR
        / "documents"
        / "Company Profile Presentation .pdf"
    )

    if not pdf_path.exists():
        abort(404)

    return send_file(
        pdf_path,
        mimetype="application/pdf",
        as_attachment=False
    )
 
# ============================================================
# LEGAL PAGES
# ============================================================

@app.route("/privacy-policy", methods=["GET"], strict_slashes=False)
def privacy_policy():
    """Public Privacy Policy page."""
    privacy_file = TEMPLATES_DIR / "privacy_policy.html"

    if not privacy_file.is_file():
        app.logger.error("Privacy Policy template not found: %s", privacy_file)
        return "Privacy Policy page not found.", 404

    return render_template(
        "privacy_policy.html",
        company_name=COMPANY_NAME,
        company_email=COMPANY_EMAIL,
        company_tagline=COMPANY_TAGLINE
    )


@app.route("/terms", methods=["GET"], strict_slashes=False)
def terms():
    """Public Terms and Conditions page."""
    terms_file = TEMPLATES_DIR / "terms.html"

    if not terms_file.is_file():
        app.logger.error("Terms template not found: %s", terms_file)
        return "Terms page not found.", 404

    return render_template(
        "terms.html",
        company_name=COMPANY_NAME,
        company_email=COMPANY_EMAIL,
        company_tagline=COMPANY_TAGLINE
    )
# ============================================================
# TRAINING PROGRAM APPLICATION
# ============================================================

@app.route(
    "/training/apply",
    methods=["GET", "POST"]
)
def training_apply():

    # --------------------------------------------------------
    # DISPLAY FORM
    # --------------------------------------------------------

    if request.method == "GET":

        return render_template(
            "training_apply.html"
        )


    # --------------------------------------------------------
    # READ FORM
    # --------------------------------------------------------

    full_name = request.form.get(
        "full_name",
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

    program = request.form.get(
        "program",
        ""
    ).strip()

    education = request.form.get(
        "education",
        ""
    ).strip()

    company = request.form.get(
        "company",
        ""
    ).strip()

    experience = request.form.get(
        "experience",
        ""
    ).strip()

    motivation = request.form.get(
        "motivation",
        ""
    ).strip()

    message = request.form.get(
        "message",
        ""
    ).strip()

    agreement = request.form.get(
        "agreement",
        ""
    ).strip()


    # --------------------------------------------------------
    # REQUIRED FIELD VALIDATION
    # --------------------------------------------------------

    if not full_name:

        flash(
            "Full name is required.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if not email:

        flash(
            "Email address is required.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if not phone:

        flash(
            "Phone number is required.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if not program:

        flash(
            "Please select a training program.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if not motivation:

        flash(
            "Please explain why you want to join the training program.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if agreement != "1":

        flash(
            "Please confirm the application declaration.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    # --------------------------------------------------------
    # BASIC LENGTH VALIDATION
    # --------------------------------------------------------

    if len(full_name) > 120:

        flash(
            "Full name is too long.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if len(email) > 150:

        flash(
            "Email address is too long.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if len(phone) > 30:

        flash(
            "Phone number is too long.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if len(education) > 150:

        flash(
            "Educational background is too long.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if len(company) > 150:

        flash(
            "Company or organization name is too long.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if len(experience) > 1000:

        flash(
            "Previous experience is too long.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if len(motivation) > 1500:

        flash(
            "Motivation message is too long.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    if len(message) > 1000:

        flash(
            "Additional information is too long.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )


    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    created_at = utc_now()

    db = get_db()

    try:

        application_id = (
            generate_training_application_id(
                db
            )
        )


        cursor = db.execute(
            """
            INSERT INTO training_applications (
                application_id,
                full_name,
                email,
                phone,
                program,
                education,
                company,
                experience,
                motivation,
                message,
                status,
                created_at,
                updated_at,
                email_sent
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                'New',
                ?, ?,
                0
            )
            """,
            (
                application_id,
                full_name,
                email,
                phone,
                program,
                education,
                company,
                experience,
                motivation,
                message,
                created_at,
                created_at
            )
        )


        application_db_id = cursor.lastrowid


        application = db.execute(
            """
            SELECT *
            FROM training_applications
            WHERE id = ?
            LIMIT 1
            """,
            (
                application_db_id,
            )
        ).fetchone()


        db.commit()


    except Exception:

        db.rollback()

        app.logger.exception(
            "Failed to save training application."
        )

        flash(
            "We could not submit your application. Please try again.",
            "danger"
        )

        return redirect(
            url_for("training_apply")
        )

    finally:

        close_db(db)


    # --------------------------------------------------------
    # ACTIVITY LOG
    # --------------------------------------------------------

    try:

        log_activity(
            "public",
            None,
            "training_application",
            (
                "New training application received. "
                f"Application ID: {application_id}. "
                f"Program: {program}."
            )
        )

    except Exception:

        app.logger.exception(
            "Failed to log training application activity."
        )


    # --------------------------------------------------------
    # EMAIL COMPANY
    # --------------------------------------------------------

    email_sent = False

    if (
        os.getenv("MAIL_SERVER")
        and os.getenv("MAIL_USERNAME")
        and os.getenv("MAIL_PASSWORD")
    ):

        email_sent, _ = send_training_application_email(
            application
        )


        db = get_db()

        try:

            db.execute(
                """
                UPDATE training_applications
                SET
                    email_sent = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    1 if email_sent else 0,
                    utc_now(),
                    application_db_id
                )
            )

            db.commit()

        except Exception:

            db.rollback()

            app.logger.exception(
                "Failed to update training email status."
            )

        finally:

            close_db(db)


    # --------------------------------------------------------
    # SUCCESS
    # --------------------------------------------------------

    flash(
        (
            "Your training application has been submitted "
            "successfully. Your application reference is "
            f"{application_id}."
        ),
        "success"
    )


    return redirect(
        url_for("training_apply")
    )

# ============================================================
# PUBLIC CONSULTATION API
# ============================================================

@app.route(
    "/api/consultation",
    methods=["POST"]
)
def consultation_api():

    data = (
        request.get_json(silent=True)
        or request.form
    )

    name = str(
        data.get("name", "")
    ).strip()

    email = str(
        data.get("email", "")
    ).strip()

    phone = str(
        data.get("phone", "")
    ).strip()

    company = str(
        data.get("company", "")
    ).strip()

    service = str(
        data.get("service", "")
    ).strip()

    message = str(
        data.get("message", "")
    ).strip()

    language = str(
        data.get("language", "en")
    ).strip() or "en"


    # ========================================================
    # VALIDATION
    # ========================================================

    if not name:
        return jsonify(
            success=False,
            message="Name is required."
        ), 400

    if not phone:
        return jsonify(
            success=False,
            message="Phone is required."
        ), 400

    if not service:
        return jsonify(
            success=False,
            message="Service is required."
        ), 400


    created_at = utc_now()

    db = get_db()

    try:

        # ====================================================
        # 1. SAVE CONSULTATION
        # ====================================================

        cursor = db.execute(
            """
            INSERT INTO consultations (
                name,
                email,
                phone,
                company,
                service,
                message,
                language,
                status,
                created_at,
                updated_at,
                email_sent
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?,
                'New',
                ?, ?,
                0
            )
            """,
            (
                name,
                email,
                phone,
                company,
                service,
                message,
                language,
                created_at,
                created_at
            )
        )

        consultation_id = cursor.lastrowid


        # ====================================================
        # GET SAVED CONSULTATION
        # ====================================================

        consultation = db.execute(
            """
            SELECT *
            FROM consultations
            WHERE id = ?
            LIMIT 1
            """,
            (consultation_id,)
        ).fetchone()


        # ====================================================
        # 2. NOTIFY ACTIVE STAFF
        # ====================================================

        staff_members = db.execute(
            """
            SELECT id
            FROM staff
            WHERE status = 'Active'
            """
        ).fetchall()


        for staff_member in staff_members:

            db.execute(
                """
                INSERT INTO notifications (
                    staff_id,
                    title,
                    message,
                    is_read,
                    created_at
                )
                VALUES (?, ?, ?, 0, ?)
                """,
                (
                    staff_member["id"],
                    "New consultation request",
                    (
                        f"{name} submitted a "
                        f"{service} consultation."
                    ),
                    created_at
                )
            )


        # ====================================================
        # 3. ACTIVITY LOG
        # ====================================================

        db.execute(
            """
            INSERT INTO activity_logs (
                actor_type,
                actor_id,
                action,
                description,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                "customer",
                None,
                "consultation_submitted",
                (
                    f"Consultation #{consultation_id} "
                    f"submitted by {name}."
                ),
                created_at
            )
        )


        db.commit()


    except Exception as error:

        db.rollback()

        print(
            "[CONSULTATION DATABASE ERROR]",
            error
        )

        return jsonify(
            success=False,
            message="Could not save consultation request."
        ), 500

    finally:

        close_db(db)


    # ========================================================
    # 4. SEND EMAIL TO COMPANY
    # ========================================================

    email_sent = False

    if (
        os.getenv("MAIL_SERVER")
        and os.getenv("MAIL_USERNAME")
        and os.getenv("MAIL_PASSWORD")
    ):

        try:

            email_sent, _ = send_consultation_email(
                consultation
            )

        except Exception as error:

            print(
                "[CONSULTATION EMAIL ERROR]",
                error
            )

            email_sent = False


    # ========================================================
    # 5. RECORD EMAIL STATUS
    # ========================================================

    db = get_db()

    try:

        db.execute(
            """
            UPDATE consultations
            SET email_sent = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                1 if email_sent else 0,
                utc_now(),
                consultation_id
            )
        )

        db.commit()

    except Exception as error:

        db.rollback()

        print(
            "[CONSULTATION EMAIL STATUS ERROR]",
            error
        )

    finally:

        close_db(db)


    # ========================================================
    # SUCCESS
    # ========================================================

    return jsonify(
        success=True,
        message="Consultation request received.",
        consultation_id=consultation_id,
        email_sent=email_sent
    )


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


    if not all([
        first_name,
        last_name,
        phone,
        department,
        position,
        password,
        confirm_password,
    ]):

        flash(
            "All required fields must be completed.",
            "danger"
        )

        return redirect(
            url_for("staff_register")
        )


    if len(password) < 8:

        flash(
            "Password must be at least 8 characters.",
            "danger"
        )

        return redirect(
            url_for("staff_register")
        )


    if password != confirm_password:

        flash(
            "Passwords do not match.",
            "danger"
        )

        return redirect(
            url_for("staff_register")
        )


    db = get_db()

    try:

        duplicate = db.execute(
            """
            SELECT id
            FROM staff
            WHERE phone = ?
            LIMIT 1
            """,
            (phone,)
        ).fetchone()

        if duplicate:

            flash(
                "A staff registration already exists with this phone number.",
                "danger"
            )

            return redirect(
                url_for("staff_register")
            )


        staff_id = generate_staff_id(
            db
        )

        email = generate_staff_email(
            first_name,
            last_name,
            staff_id
        )


        cursor = db.execute(
            """
            INSERT INTO staff (
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
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, 'Pending', ?
            )
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
                utc_now()
            )
        )

        staff_db_id = cursor.lastrowid

        db.commit()


        log_activity(
            "staff",
            staff_db_id,
            "staff_registration",
            (
                f"Staff registration received "
                f"for {staff_id}."
            )
        )


        flash(
            (
                f"Registration submitted successfully. "
                f"Your Staff ID is {staff_id}. "
                f"Your account is awaiting approval."
            ),
            "success"
        )

    except sqlite3.IntegrityError:

        db.rollback()

        flash(
            "Unable to complete registration. Please try again.",
            "danger"
        )

    finally:

        close_db(db)


    return redirect(
        url_for("staff_login")
    )


# ============================================================
# STAFF LOGIN
# ============================================================

@app.route(
    "/staff/login",
    methods=["GET", "POST"]
)
def staff_login():

    if request.method == "GET":

        return render_template(
            "staff_login.html"
        )


    identifier = (
        request.form.get("login")
        or request.form.get("email")
        or request.form.get("staff_id")
        or ""
    ).strip()


    password = (
        request.form.get("password")
        or ""
    )


    if not identifier or not password:

        flash(
            "Work Email or Staff ID and password are required.",
            "danger"
        )

        return redirect(
            url_for("staff_login")
        )


    db = get_db()

    try:

        staff = db.execute(
            """
            SELECT *
            FROM staff
            WHERE
                UPPER(TRIM(staff_id)) = UPPER(TRIM(?))
                OR (
                    email IS NOT NULL
                    AND TRIM(email) != ''
                    AND LOWER(TRIM(email)) = LOWER(TRIM(?))
                )
            LIMIT 1
            """,
            (
                identifier,
                identifier
            )
        ).fetchone()


        if not staff:

            flash(
                "Invalid Staff ID/email or password.",
                "danger"
            )

            return redirect(
                url_for("staff_login")
            )


        if not check_password_hash(
            staff["password_hash"],
            password
        ):

            flash(
                "Invalid Staff ID/email or password.",
                "danger"
            )

            return redirect(
                url_for("staff_login")
            )


        status = (
            staff["status"]
            or ""
        ).strip().lower()


        if status != "active":

            if status == "pending":

                flash(
                    "Your staff account is still awaiting approval.",
                    "warning"
                )

            elif status == "rejected":

                flash(
                    "Your staff registration was rejected.",
                    "danger"
                )

            elif status == "disabled":

                flash(
                    "Your staff account is disabled.",
                    "danger"
                )

            else:

                flash(
                    "Your staff account is not active.",
                    "danger"
                )

            return redirect(
                url_for("staff_login")
            )


        db.execute(
            """
            UPDATE staff
            SET last_login = ?
            WHERE id = ?
            """,
            (
                utc_now(),
                staff["id"]
            )
        )

        db.commit()


        session.clear()

        session["staff_db_id"] = staff["id"]

        session["staff_id"] = staff["staff_id"]

        session["staff_email"] = (
            staff["email"]
            or ""
        )

        session["staff_logged_in"] = True


        log_activity(
            "staff",
            staff["id"],
            "staff_login",
            "Staff member logged in."
        )


        return redirect(
            url_for("staff_dashboard")
        )


    finally:

        close_db(db)


# ============================================================
# STAFF DASHBOARD
# ============================================================

@app.route("/staff/dashboard")
@staff_required
def staff_dashboard():

    staff = current_staff()

    db = get_db()

    try:

        consultations = db.execute(
            """
            SELECT
                c.*,

                s.first_name AS assigned_first_name,
                s.last_name AS assigned_last_name,
                s.staff_id AS assigned_staff_code

            FROM consultations c

            LEFT JOIN staff s
                ON s.id = COALESCE(
                    c.assigned_staff_id,
                    c.assigned_to
                )

            WHERE COALESCE(
                c.assigned_staff_id,
                c.assigned_to
            ) = ?

            ORDER BY c.id DESC
            """,
            (
                staff["id"],
            )
        ).fetchall()


        notifications = db.execute(
            """
            SELECT *
            FROM notifications

            WHERE staff_id = ?

            ORDER BY id DESC

            LIMIT 15
            """,
            (
                staff["id"],
            )
        ).fetchall()


    finally:

        close_db(db)


    assigned_count = len(consultations)

    in_progress_count = sum(
        1
        for consultation in consultations
        if (
            consultation["status"] or ""
        ).lower().replace("_", " ") in {
            "in progress",
            "assigned",
            "pending"
        }
    )

    closed_count = sum(
        1
        for consultation in consultations
        if (
            consultation["status"] or ""
        ).lower().replace("_", " ") in {
            "closed",
            "completed",
            "complete",
            "resolved"
        }
    )


    return render_template(
        "staff_dashboard.html",

        staff=staff,

        consultations=consultations,

        assigned_requests=consultations,

        notifications=notifications,

        assigned_count=assigned_count,

        in_progress_count=in_progress_count,

        closed_count=closed_count,

        completed_count=closed_count
    )


# ============================================================
# STAFF CONSULTATIONS
# ============================================================

@app.route("/staff/consultations")
@staff_required
def staff_consultations():

    staff = current_staff()

    db = get_db()

    try:

        consultations = db.execute(
            """
            SELECT
                c.*,

                s.first_name AS assigned_first_name,
                s.last_name AS assigned_last_name,
                s.staff_id AS assigned_staff_code

            FROM consultations c

            LEFT JOIN staff s
                ON s.id = COALESCE(
                    c.assigned_staff_id,
                    c.assigned_to
                )

            WHERE COALESCE(
                c.assigned_staff_id,
                c.assigned_to
            ) = ?

            ORDER BY c.id DESC
            """,
            (
                staff["id"],
            )
        ).fetchall()

    finally:

        close_db(db)


    return render_template(
        "staff_consultations.html",

        consultations=consultations,

        staff=staff
    )


# ============================================================
# STAFF CONSULTATION DETAIL
# ============================================================

@app.route(
    "/staff/consultations/<int:consultation_id>"
)
@staff_required
def staff_consultation_view(
    consultation_id
):

    staff = current_staff()

    db = get_db()

    try:

        consultation = db.execute(
            """
            SELECT
                c.*,

                s.first_name AS assigned_first_name,
                s.last_name AS assigned_last_name,
                s.staff_id AS assigned_staff_code,
                s.email AS assigned_staff_email

            FROM consultations c

            LEFT JOIN staff s
                ON s.id = COALESCE(
                    c.assigned_staff_id,
                    c.assigned_to
                )

            WHERE c.id = ?

              AND COALESCE(
                  c.assigned_staff_id,
                  c.assigned_to
              ) = ?

            LIMIT 1
            """,
            (
                consultation_id,
                staff["id"]
            )
        ).fetchone()

    finally:

        close_db(db)


    if not consultation:

        flash(
            "Consultation not found.",
            "danger"
        )

        return redirect(
            url_for("staff_consultations")
        )


    return render_template(
        "staff_consultation_view.html",

        consultation=consultation,

        staff=staff
    )


# ============================================================
# STAFF CONSULTATION STATUS
# ============================================================

@app.route(
    "/staff/consultations/<int:consultation_id>/status",
    methods=["POST"]
)
@staff_required
def staff_consultation_status(
    consultation_id
):

    staff = current_staff()

    status = request.form.get(
        "status",
        "New"
    ).strip()

    if status not in CONSULTATION_STATUSES:

        status = "New"


    db = get_db()

    try:

        consultation = db.execute(
            """
            SELECT id
            FROM consultations
            WHERE id = ?
              AND assigned_staff_id = ?
            """,
            (
                consultation_id,
                staff["id"]
            )
        ).fetchone()

        if not consultation:

            flash(
                "Consultation not found.",
                "danger"
            )

            return redirect(
                url_for("staff_consultations")
            )


        db.execute(
            """
            UPDATE consultations
            SET status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                utc_now(),
                consultation_id
            )
        )

        db.commit()

    finally:

        close_db(db)


    log_activity(
        "staff",
        staff["id"],
        "consultation_status",
        (
            f"Consultation #{consultation_id} "
            f"changed to {status}."
        )
    )


    flash(
        "Consultation status updated.",
        "success"
    )

    return redirect(
        url_for(
            "staff_consultation_view",
            consultation_id=consultation_id
        )
    )


staff_update_consultation_status = staff_consultation_status


# ============================================================
# STAFF NOTIFICATION READ
# ============================================================

@app.route(
    "/staff/notifications/<int:notification_id>/read",
    methods=["POST"]
)
@staff_required
def mark_notification_read(
    notification_id
):

    staff = current_staff()

    db = get_db()

    try:

        db.execute(
            """
            UPDATE notifications
            SET is_read = 1
            WHERE id = ?
              AND staff_id = ?
            """,
            (
                notification_id,
                staff["id"]
            )
        )

        db.commit()

    finally:

        close_db(db)


    return redirect(
        request.referrer
        or url_for("staff_dashboard")
    )


# ============================================================
# STAFF PROFILE
# ============================================================

@app.route(
    "/staff/profile",
    methods=["GET", "POST"]
)
@staff_required
def staff_profile():
    staff = current_staff()

    if not staff:
        session.clear()
        return redirect(url_for("staff_login"))

    if request.method == "POST":
        uploaded_file = request.files.get("profile_photo")

        if not uploaded_file or not uploaded_file.filename:
            flash("Please select a profile photo to upload.", "danger")
            return redirect(url_for("staff_profile"))

        original_name = uploaded_file.filename.strip()
        if "." not in original_name:
            flash("Please upload a JPG, JPEG, PNG, or WEBP image.", "danger")
            return redirect(url_for("staff_profile"))

        extension = original_name.rsplit(".", 1)[1].lower()
        if extension not in ALLOWED_PROFILE_EXTENSIONS:
            flash("Only JPG, JPEG, PNG, and WEBP profile photos are allowed.", "danger")
            return redirect(url_for("staff_profile"))

        try:
            photo_bytes = uploaded_file.read()
        except Exception:
            photo_bytes = b""

        if not photo_bytes:
            flash("The selected photo could not be read.", "danger")
            return redirect(url_for("staff_profile"))

        if len(photo_bytes) > MAX_PROFILE_PHOTO_SIZE:
            flash("Profile photo must not exceed 5 MB.", "danger")
            return redirect(url_for("staff_profile"))

        filename = f"staff_{staff['id']}_{secrets.token_hex(16)}.{secure_filename(extension)}"
        photo_path = PROFILE_PHOTO_DIR / filename

        try:
            photo_path.write_bytes(photo_bytes)
        except Exception:
            app.logger.exception("Failed to save staff profile photo.")
            flash("The profile photo could not be saved. Please try again.", "danger")
            return redirect(url_for("staff_profile"))

        old_filename = staff["profile_photo"]
        db = get_db()
        try:
            db.execute(
                "UPDATE staff SET profile_photo = ? WHERE id = ?",
                (filename, staff["id"])
            )
            db.commit()
        except Exception:
            db.rollback()
            try:
                photo_path.unlink(missing_ok=True)
            except Exception:
                pass
            app.logger.exception("Failed to update staff profile photo record.")
            flash("The profile photo could not be saved. Please try again.", "danger")
            return redirect(url_for("staff_profile"))
        finally:
            close_db(db)

        if old_filename and old_filename != filename:
            old_path = PROFILE_PHOTO_DIR / secure_filename(old_filename)
            try:
                if old_path.is_file():
                    old_path.unlink()
            except Exception:
                app.logger.warning("Could not remove old profile photo: %s", old_path)

        log_activity(
            "staff",
            staff["id"],
            "profile_photo_updated",
            "Staff member updated their profile photo."
        )
        flash("Profile photo updated successfully.", "success")
        return redirect(url_for("staff_profile"))

    # Always fetch fresh staff data so a promotion/position change is shown immediately.
    staff = current_staff()
    return render_template("staff_profile.html", staff=staff)


@app.route("/staff/profile-photo/<filename>")
@staff_required
def staff_profile_photo(filename):
    staff = current_staff()
    if not staff:
        abort(404)

    requested_filename = secure_filename(filename)
    if not requested_filename:
        abort(404)

    if not staff["profile_photo"] or staff["profile_photo"] != requested_filename:
        abort(404)

    photo_path = PROFILE_PHOTO_DIR / requested_filename
    if not photo_path.is_file():
        abort(404)

    return send_from_directory(PROFILE_PHOTO_DIR, requested_filename)


# ============================================================
# STAFF LOGOUT
# ============================================================

@app.route("/staff/logout")
def staff_logout():

    staff = current_staff()

    if staff:

        log_activity(
            "staff",
            staff["id"],
            "staff_logout",
            "Staff member logged out."
        )

    session.clear()

    flash(
        "You have been logged out.",
        "success"
    )

    return redirect(
        url_for("staff_login")
    )


# ============================================================
# PASSWORD RESET
# ============================================================

def make_reset_token():
    return secrets.token_urlsafe(32)

def hash_reset_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

def password_reset_url(token):
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/reset-password/{token}"
    return url_for("reset_password", token=token, _external=True)


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "GET":
        return render_template("forgot_password.html")

    email = request.form.get("email", "").strip().lower()
    if not email:
        flash("Please enter your email address.", "danger")
        return render_template("forgot_password.html")

    generic_message = (
        "If an account with that email exists, a password reset link has been sent. "
        "Please check the inbox."
    )

    db = get_db()
    try:
        account = db.execute(
            """SELECT id, first_name, email FROM staff
               WHERE email IS NOT NULL AND TRIM(email) != ''
               AND LOWER(TRIM(email)) = LOWER(TRIM(?)) LIMIT 1""",
            (email,)
        ).fetchone()
        account_type = "staff" if account else None

        if not account:
            account = db.execute(
                """SELECT id, first_name, email FROM admins
                   WHERE LOWER(TRIM(email)) = LOWER(TRIM(?)) LIMIT 1""",
                (email,)
            ).fetchone()
            account_type = "admin" if account else None

        if account and account_type:
            db.execute(
                """UPDATE password_reset_tokens SET used_at = ?
                   WHERE account_type = ? AND account_id = ? AND used_at IS NULL""",
                (utc_now(), account_type, account["id"])
            )

            raw_token = make_reset_token()
            db.execute(
                """INSERT INTO password_reset_tokens
                   (account_type, account_id, token_hash, expires_at, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    account_type,
                    account["id"],
                    hash_reset_token(raw_token),
                    (datetime.now(timezone.utc) + timedelta(minutes=RESET_TOKEN_MINUTES)).isoformat(),
                    utc_now()
                )
            )
            db.commit()

            reset_link = password_reset_url(raw_token)
            first_name = account["first_name"] or "there"
            send_email(
                account["email"],
                f"{COMPANY_NAME} - Password Reset",
                f"""Dear {first_name},

A request was made to reset your {COMPANY_NAME} portal password.

Use the secure link below to create a new password:

{reset_link}

This link expires in {RESET_TOKEN_MINUTES} minutes and can only be used once.

If you did not request this password reset, you can safely ignore this email.

Regards,
{COMPANY_NAME}
Portal Administration
"""
            )

            log_activity(
                account_type,
                account["id"],
                "password_reset_requested",
                "Password reset link requested."
            )
    except Exception:
        db.rollback()
        app.logger.exception("Password reset request failed.")
    finally:
        close_db(db)

    flash(generic_message, "success")
    return render_template("forgot_password.html")


@app.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    if not token or len(token) > 200:
        flash("This password reset link is invalid or has expired.", "danger")
        return redirect(url_for("forgot_password"))

    db = get_db()
    try:
        record = db.execute(
            "SELECT * FROM password_reset_tokens WHERE token_hash = ? LIMIT 1",
            (hash_reset_token(token),)
        ).fetchone()

        if not record:
            flash("This password reset link is invalid or has expired.", "danger")
            return redirect(url_for("forgot_password"))

        if record["used_at"]:
            flash("This password reset link has already been used.", "danger")
            return redirect(url_for("forgot_password"))

        try:
            expires_at = datetime.fromisoformat(record["expires_at"])
        except (TypeError, ValueError):
            expires_at = datetime.min.replace(tzinfo=timezone.utc)

        if expires_at <= datetime.now(timezone.utc):
            db.execute("UPDATE password_reset_tokens SET used_at = ? WHERE id = ?", (utc_now(), record["id"]))
            db.commit()
            flash("This password reset link has expired. Please request a new one.", "danger")
            return redirect(url_for("forgot_password"))

        if request.method == "GET":
            return render_template("reset_password.html", token=token)

        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        if len(password) < 8:
            flash("Password must be at least 8 characters.", "danger")
            return render_template("reset_password.html", token=token)
        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template("reset_password.html", token=token)

        password_hash = generate_password_hash(password)
        account_type = record["account_type"]
        account_id = record["account_id"]

        if account_type == "staff":
            db.execute("UPDATE staff SET password_hash = ? WHERE id = ?", (password_hash, account_id))
            login_endpoint = "staff_login"
        elif account_type == "admin":
            db.execute("UPDATE admins SET password_hash = ? WHERE id = ?", (password_hash, account_id))
            login_endpoint = "admin_login"
        else:
            flash("This password reset link is invalid.", "danger")
            return redirect(url_for("forgot_password"))

        now = utc_now()
        db.execute("UPDATE password_reset_tokens SET used_at = ? WHERE account_type = ? AND account_id = ? AND used_at IS NULL", (now, account_type, account_id))
        db.commit()

        log_activity(account_type, account_id, "password_reset_completed", "Portal password was reset successfully.")
        flash("Your password has been reset successfully. You can now log in.", "success")
        return redirect(url_for(login_endpoint))

    except Exception:
        db.rollback()
        app.logger.exception("Password reset failed.")
        flash("We could not reset your password. Please request a new reset link.", "danger")
        return redirect(url_for("forgot_password"))
    finally:
        close_db(db)


# ============================================================
# ADMIN LOGIN
# ============================================================

@app.route(
    "/admin/login",
    methods=["GET", "POST"]
)
def admin_login():

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


    if not email or not password:

        flash(
            "Email and password are required.",
            "danger"
        )

        return render_template(
            "admin_login.html"
        )


    db = get_db()

    try:

        admin = db.execute(
            """
            SELECT *
            FROM admins
            WHERE LOWER(email) = LOWER(?)
            LIMIT 1
            """,
            (
                email,
            )
        ).fetchone()


        if not admin:

            flash(
                "Invalid email or password.",
                "danger"
            )

            return render_template(
                "admin_login.html"
            )


        if not check_password_hash(
            admin["password_hash"],
            password
        ):

            flash(
                "Invalid email or password.",
                "danger"
            )

            return render_template(
                "admin_login.html"
            )


        if admin["status"] != "Active":

            flash(
                "This administrator account is not active.",
                "danger"
            )

            return render_template(
                "admin_login.html"
            )


        db.execute(
            """
            UPDATE admins
            SET last_login = ?
            WHERE id = ?
            """,
            (
                utc_now(),
                admin["id"]
            )
        )

        db.commit()


        session.clear()

        session["admin_id"] = admin["id"]
        session["admin_email"] = admin["email"]


    finally:

        close_db(db)


    log_activity(
        "admin",
        admin["id"],
        "admin_login",
        "Administrator logged in."
    )


    return redirect(
        url_for("admin_dashboard")
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():

    db = get_db()

    try:

        total_staff = db.execute(
            """
            SELECT COUNT(*)
            FROM staff
            """
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
              AND assigned_to IS NULL
            """
        ).fetchone()[0]

        assigned_consultations = db.execute(
            """
            SELECT COUNT(*)
            FROM consultations
            WHERE assigned_staff_id IS NOT NULL
               OR assigned_to IS NOT NULL
            """
        ).fetchone()[0]


        recent_consultations = db.execute(
            """
            SELECT
                c.*,

                s.first_name AS assigned_first_name,
                s.last_name AS assigned_last_name,
                s.email AS assigned_staff_email,
                s.staff_id AS assigned_staff_code,

                s.first_name AS staff_first_name,
                s.last_name AS staff_last_name,
                s.email AS staff_email

            FROM consultations c

            LEFT JOIN staff s
                ON s.id = COALESCE(
                    c.assigned_staff_id,
                    c.assigned_to
                )

            ORDER BY c.id DESC
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


        stats = {
            "total_staff": total_staff,
            "active_staff": active_staff,
            "pending_staff": pending_staff,
            "disabled_staff": disabled_staff,

            "total_consultations": total_consultations,
            "new_consultations": new_consultations,
            "in_progress_consultations": in_progress_consultations,
            "closed_consultations": closed_consultations,
            "unassigned_consultations": unassigned_consultations,
            "assigned_consultations": assigned_consultations,
        }

    finally:

        close_db(db)


    return render_template(
        "admin_dashboard.html",

        total_staff=total_staff,
        active_staff=active_staff,
        pending_staff=pending_staff,
        disabled_staff=disabled_staff,

        total_consultations=total_consultations,
        new_consultations=new_consultations,
        in_progress_consultations=in_progress_consultations,
        closed_consultations=closed_consultations,

        unassigned_consultations=unassigned_consultations,
        assigned_consultations=assigned_consultations,

        recent_consultations=recent_consultations,
        recent_staff=recent_staff,

        stats=stats
    )


# ============================================================
# ADMIN STAFF LIST
# ============================================================

@app.route("/admin/staff")
@admin_required
def admin_staff():

    db = get_db()

    try:

        staff = db.execute(
            """
            SELECT *
            FROM staff
            ORDER BY id DESC
            """
        ).fetchall()

    finally:

        close_db(db)


    return render_template(
        "admin_staff.html",
        staff=staff
    )


# ============================================================
# ADMIN STAFF VIEW
# ============================================================

@app.route(
    "/admin/staff/<int:staff_id>"
)
@admin_required
def admin_staff_view(
    staff_id
):

    db = get_db()

    try:

        staff = db.execute(
            """
            SELECT *
            FROM staff
            WHERE id = ?
            LIMIT 1
            """,
            (
                staff_id,
            )
        ).fetchone()

    finally:

        close_db(db)


    if not staff:

        flash(
            "Staff member not found.",
            "danger"
        )

        return redirect(
            url_for("admin_staff")
        )


    return render_template(
        "admin_staff_view.html",
        staff=staff
    )


# ============================================================
# ADMIN STAFF ACTION
# ============================================================

@app.route(
    "/admin/staff/<int:staff_id>/action",
    methods=["POST"]
)
@admin_required
def admin_staff_action(
    staff_id
):

    action = request.form.get(
        "action",
        ""
    ).strip().lower()


    if action not in (
        "approve",
        "reject",
        "disable",
        "activate",
    ):

        flash(
            "Invalid staff action.",
            "danger"
        )

        return redirect(
            url_for(
                "admin_staff_view",
                staff_id=staff_id
            )
        )


    db = get_db()

    try:

        staff = db.execute(
            """
            SELECT *
            FROM staff
            WHERE id = ?
            LIMIT 1
            """,
            (
                staff_id,
            )
        ).fetchone()


        if not staff:

            flash(
                "Staff member not found.",
                "danger"
            )

            return redirect(
                url_for("admin_staff")
            )


        new_status = {
            "approve": "Active",
            "reject": "Rejected",
            "disable": "Disabled",
            "activate": "Active",
        }[action]


        email = staff["email"]


        if (
            action in ("approve", "activate")
            and not email
        ):

            email = generate_staff_email(
                staff["first_name"],
                staff["last_name"],
                staff["staff_id"]
            )


        if action in (
            "approve",
            "activate"
        ):

            db.execute(
                """
                UPDATE staff
                SET status = ?,
                    email = COALESCE(?, email),
                    approved_at = COALESCE(
                        approved_at,
                        ?
                    )
                WHERE id = ?
                """,
                (
                    new_status,
                    email,
                    utc_now(),
                    staff_id
                )
            )

        else:

            db.execute(
                """
                UPDATE staff
                SET status = ?
                WHERE id = ?
                """,
                (
                    new_status,
                    staff_id
                )
            )


        db.commit()


    finally:

        close_db(db)


    action_description = {
        "approve": "Staff account approved.",
        "reject": "Staff account rejected.",
        "disable": "Staff account disabled.",
        "activate": "Staff account activated.",
    }[action]


    log_activity(
        "admin",
        session["admin_id"],
        f"staff_{action}",
        (
            f"{action_description} "
            f"Staff ID: {staff['staff_id']}"
        )
    )


    if action in (
        "approve",
        "activate"
    ):

        create_notification(
            staff_id,
            "Account Activated",
            (
                "Your Novera staff account "
                "has been activated."
            )
        )


        if email:

            send_email(
                email,
                "Novera Staff Account Activated",
                f"""
{COMPANY_NAME}

Your staff account has been activated.

Staff ID:
{staff["staff_id"]}

You can now log in to the staff portal.
"""
            )


    flash(
        action_description,
        "success"
    )


    return redirect(
        url_for(
            "admin_staff_view",
            staff_id=staff_id
        )
    )


# ============================================================
# ADMIN STAFF PROMOTION
# ============================================================

@app.route("/admin/staff/<int:staff_id>/promote", methods=["POST"])
@admin_required
def admin_staff_promote(staff_id):
    new_position = request.form.get("position", "").strip()
    new_department = request.form.get("department", "").strip()
    if not new_position:
        flash("Please enter the new position.", "danger")
        return redirect(url_for("admin_staff_view", staff_id=staff_id))

    db = get_db()
    try:
        staff = db.execute("SELECT * FROM staff WHERE id = ? LIMIT 1", (staff_id,)).fetchone()
        if not staff:
            flash("Staff member not found.", "danger")
            return redirect(url_for("admin_staff"))
        old_position = staff["position"] or "Not assigned"
        old_department = staff["department"] or "Not assigned"
        if new_department:
            db.execute("UPDATE staff SET position = ?, department = ? WHERE id = ?", (new_position, new_department, staff_id))
        else:
            db.execute("UPDATE staff SET position = ? WHERE id = ?", (new_position, staff_id))
        db.commit()
    finally:
        close_db(db)

    log_activity("admin", session["admin_id"], "staff_promoted", f"Staff ID {staff['staff_id']} promoted. Position: {old_position} -> {new_position}. Department: {old_department} -> {new_department or old_department}.")
    create_notification(staff_id, "Position Updated", f"Your position has been updated to {new_position}." + (f" Department: {new_department}." if new_department else ""))
    if staff["email"]:
        send_email(staff["email"], f"{COMPANY_NAME} - Position Updated", f"Dear {staff['first_name']},\n\nYour position in the {COMPANY_NAME} staff portal has been updated.\n\nNew Position:\n{new_position}\n\n" + (f"Department:\n{new_department}\n\n" if new_department else "") + f"Your updated details will appear automatically in your staff portal.\n\nRegards,\n{COMPANY_NAME}\nPortal Administration\n")
    flash(f"{staff['first_name']} {staff['last_name']} has been promoted successfully.", "success")
    return redirect(url_for("admin_staff_view", staff_id=staff_id))


# ============================================================
# ADMIN CONSULTATIONS
# ============================================================

@app.route("/admin/consultations")
@admin_required
def admin_consultations():

    db = get_db()

    try:

        consultations = db.execute(
            """
            SELECT
                c.*,

                s.first_name AS assigned_first_name,
                s.last_name AS assigned_last_name,
                s.email AS assigned_staff_email,
                s.staff_id AS assigned_staff_code,

                s.first_name AS staff_first_name,
                s.last_name AS staff_last_name,
                s.email AS staff_email

            FROM consultations c

            LEFT JOIN staff s
                ON s.id = COALESCE(
                    c.assigned_staff_id,
                    c.assigned_to
                )

            ORDER BY c.id DESC
            """
        ).fetchall()

    finally:

        close_db(db)


    return render_template(
        "admin_consultations.html",
        consultations=consultations
    )


# ============================================================
# ADMIN CONSULTATION VIEW
# ============================================================

@app.route(
    "/admin/consultations/<int:consultation_id>"
)
@admin_required
def admin_consultation_view(
    consultation_id
):

    db = get_db()

    try:

        consultation = db.execute(
            """
            SELECT
                c.*,

                s.first_name AS assigned_first_name,
                s.last_name AS assigned_last_name,
                s.staff_id AS assigned_staff_code,
                s.email AS assigned_staff_email,
                s.department AS assigned_department,
                s.position AS assigned_position,

                a.first_name AS assigned_by_first_name,
                a.last_name AS assigned_by_last_name,
                a.email AS assigned_by_email

            FROM consultations c

            LEFT JOIN staff s
                ON s.id = COALESCE(
                    c.assigned_staff_id,
                    c.assigned_to
                )

            LEFT JOIN admins a
                ON a.id = c.assigned_by

            WHERE c.id = ?

            LIMIT 1
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
                email,
                department,
                position,
                status

            FROM staff

            WHERE status = 'Active'

            ORDER BY first_name, last_name
            """
        ).fetchall()

    finally:

        close_db(db)


    if not consultation:

        flash(
            "Consultation not found.",
            "danger"
        )

        return redirect(
            url_for("admin_consultations")
        )


    return render_template(
        "admin_consultation_view.html",
        consultation=consultation,
        staff=staff
    )


# ============================================================
# ADMIN CONSULTATION STATUS
# ============================================================

@app.route(
    "/admin/consultations/<int:consultation_id>/status",
    methods=["POST"]
)
@admin_required
def admin_consultation_status(
    consultation_id
):

    status = request.form.get(
        "status",
        "New"
    ).strip()


    if status not in CONSULTATION_STATUSES:

        status = "New"


    db = get_db()

    try:

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


        if not consultation:

            flash(
                "Consultation not found.",
                "danger"
            )

            return redirect(
                url_for("admin_consultations")
            )


        db.execute(
            """
            UPDATE consultations
            SET status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                utc_now(),
                consultation_id
            )
        )

        db.commit()

    finally:

        close_db(db)


    log_activity(
        "admin",
        session["admin_id"],
        "consultation_status",
        (
            f"Consultation #{consultation_id} "
            f"changed to {status}."
        )
    )


    flash(
        "Consultation status updated.",
        "success"
    )


    return redirect(
        url_for(
            "admin_consultation_view",
            consultation_id=consultation_id
        )
    )


admin_update_consultation_status = (
    admin_consultation_status
)


# ============================================================
# ADMIN CONSULTATION ASSIGN
# ============================================================

@app.route(
    "/admin/consultations/<int:consultation_id>/assign",
    methods=["POST"]
)
@admin_required
def admin_consultation_assign(
    consultation_id
):

    assigned_staff_id = request.form.get(
        "assigned_staff_id"
    )

    if not assigned_staff_id:

        assigned_staff_id = request.form.get(
            "assigned_to"
        )


    try:

        assigned_staff_id = int(
            assigned_staff_id
        )

    except (
        TypeError,
        ValueError
    ):

        flash(
            "Please select a valid staff member.",
            "danger"
        )

        return redirect(
            url_for(
                "admin_consultation_view",
                consultation_id=consultation_id
            )
        )


    db = get_db()

    try:

        consultation = db.execute(
            """
            SELECT *
            FROM consultations
            WHERE id = ?
            LIMIT 1
            """,
            (
                consultation_id,
            )
        ).fetchone()


        staff = db.execute(
            """
            SELECT *
            FROM staff
            WHERE id = ?
              AND status = 'Active'
            LIMIT 1
            """,
            (
                assigned_staff_id,
            )
        ).fetchone()


        if not consultation:

            flash(
                "Consultation not found.",
                "danger"
            )

            return redirect(
                url_for("admin_consultations")
            )


        if not staff:

            flash(
                "Selected staff member is not active.",
                "danger"
            )

            return redirect(
                url_for(
                    "admin_consultation_view",
                    consultation_id=consultation_id
                )
            )


        db.execute(
            """
            UPDATE consultations
            SET
                assigned_staff_id = ?,
                assigned_to = ?,
                assigned_by = ?,
                assigned_at = ?,
                updated_at = ?

            WHERE id = ?
            """,
            (
                staff["id"],
                staff["id"],
                session["admin_id"],
                utc_now(),
                utc_now(),
                consultation_id
            )
        )


        db.commit()


    finally:

        close_db(db)


    create_notification(
        staff["id"],
        "Consultation Assigned",
        (
            f"Consultation #{consultation_id} "
            "has been assigned to you."
        )
    )


    send_assignment_email(
        staff,
        consultation
    )


    log_activity(
        "admin",
        session["admin_id"],
        "consultation_assigned",
        (
            f"Consultation #{consultation_id} "
            f"assigned to {staff['staff_id']}."
        )
    )


    flash(
        (
            f"Consultation assigned to "
            f"{staff['first_name']} {staff['last_name']}."
        ),
        "success"
    )


    return redirect(
        url_for(
            "admin_consultation_view",
            consultation_id=consultation_id
        )
    )


admin_assign_consultation = (
    admin_consultation_assign
)


# ============================================================
# ADMIN CONSULTATION UNASSIGN
# ============================================================

@app.route(
    "/admin/consultations/<int:consultation_id>/unassign",
    methods=["POST"]
)
@admin_required
def admin_consultation_unassign(
    consultation_id
):

    db = get_db()

    try:

        consultation = db.execute(
            """
            SELECT *
            FROM consultations
            WHERE id = ?
            LIMIT 1
            """,
            (
                consultation_id,
            )
        ).fetchone()


        if not consultation:

            flash(
                "Consultation not found.",
                "danger"
            )

            return redirect(
                url_for("admin_consultations")
            )


        db.execute(
            """
            UPDATE consultations
            SET
                assigned_staff_id = NULL,
                assigned_to = NULL,
                assigned_by = NULL,
                assigned_at = NULL,
                updated_at = ?

            WHERE id = ?
            """,
            (
                utc_now(),
                consultation_id
            )
        )

        db.commit()

    finally:

        close_db(db)


    log_activity(
        "admin",
        session["admin_id"],
        "consultation_unassigned",
        (
            f"Consultation #{consultation_id} "
            "was unassigned."
        )
    )


    flash(
        "Consultation unassigned.",
        "success"
    )


    return redirect(
        url_for(
            "admin_consultation_view",
            consultation_id=consultation_id
        )
    )


admin_unassign_consultation = (
    admin_consultation_unassign
)


# ============================================================
# ADMIN CONSULTATION DELETE
# ============================================================

@app.route(
    "/admin/consultations/<int:consultation_id>/delete",
    methods=["POST"]
)
@admin_required
def admin_consultation_delete(
    consultation_id
):

    db = get_db()

    try:

        consultation = db.execute(
            """
            SELECT *
            FROM consultations
            WHERE id = ?
            LIMIT 1
            """,
            (
                consultation_id,
            )
        ).fetchone()


        if not consultation:

            flash(
                "Consultation not found.",
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
            (
                consultation_id,
            )
        )

        db.commit()

    finally:

        close_db(db)


    log_activity(
        "admin",
        session["admin_id"],
        "consultation_deleted",
        (
            f"Consultation #{consultation_id} "
            "was deleted."
        )
    )


    flash(
        "Consultation deleted.",
        "success"
    )


    return redirect(
        url_for("admin_consultations")
    )


admin_delete_consultation = (
    admin_consultation_delete
)


# ============================================================
# ADMIN LOGOUT
# ============================================================

@app.route("/admin/logout")
def admin_logout():

    admin = current_admin()

    if admin:

        log_activity(
            "admin",
            admin["id"],
            "admin_logout",
            "Administrator logged out."
        )

    session.clear()

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

    if request.method == "GET":
        return render_template(
            "md_register.html"
        )

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    confirm_password = request.form.get(
        "confirm_password",
        ""
    )

    first_name = request.form.get(
        "first_name",
        ""
    ).strip()

    last_name = request.form.get(
        "last_name",
        ""
    ).strip()


    if not email:
        flash(
            "Email address is required.",
            "danger"
        )

        return redirect(
            url_for("md_register")
        )


    if not password:
        flash(
            "Password is required.",
            "danger"
        )

        return redirect(
            url_for("md_register")
        )


    if len(password) < 8:
        flash(
            "Password must be at least 8 characters.",
            "danger"
        )

        return redirect(
            url_for("md_register")
        )


    if password != confirm_password:
        flash(
            "Passwords do not match.",
            "danger"
        )

        return redirect(
            url_for("md_register")
        )


    db = get_db()

    try:

        existing = db.execute(
            """
            SELECT id
            FROM admins
            WHERE LOWER(email) = LOWER(?)
            LIMIT 1
            """,
            (
                email,
            )
        ).fetchone()


        if existing:

            flash(
                "An account with this email already exists.",
                "danger"
            )

            return redirect(
                url_for("md_register")
            )


        db.execute(
            """
            INSERT INTO admins (
                email,
                password_hash,
                first_name,
                last_name,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, 'Active', ?)
            """,
            (
                email,
                generate_password_hash(password),
                first_name or "Management",
                last_name or "Director",
                utc_now()
            )
        )

        db.commit()


    except sqlite3.IntegrityError:

        db.rollback()

        flash(
            "An account with this email already exists.",
            "danger"
        )

        return redirect(
            url_for("md_register")
        )


    finally:

        close_db(db)


    flash(
        "Management account created successfully. You can now log in.",
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


    if not email or not password:

        flash(
            "Email and password are required.",
            "danger"
        )

        return render_template(
            "md_login.html"
        )


    db = get_db()

    try:

        md = db.execute(
            """
            SELECT *
            FROM admins
            WHERE LOWER(email) = LOWER(?)
              AND status = 'Active'
            LIMIT 1
            """,
            (
                email,
            )
        ).fetchone()


        if not md:

            flash(
                "Invalid management email or password.",
                "danger"
            )

            return render_template(
                "md_login.html"
            )


        if not check_password_hash(
            md["password_hash"],
            password
        ):

            flash(
                "Invalid management email or password.",
                "danger"
            )

            return render_template(
                "md_login.html"
            )


        session.clear()

        session["md_id"] = md["id"]
        session["md_email"] = md["email"]


    finally:

        close_db(db)


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

    try:

        # ========================================================
        # STAFF COUNTS
        # ========================================================

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


        # ========================================================
        # CONSULTATION COUNTS
        # ========================================================

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
              AND assigned_to IS NULL
            """
        ).fetchone()[0]


        # ========================================================
        # RECENT CONSULTATIONS
        # ========================================================

        recent_consultations = db.execute(
            """
            SELECT *
            FROM consultations
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()


        # ========================================================
        # RECENT STAFF
        # ========================================================

        recent_staff = db.execute(
            """
            SELECT *
            FROM staff
            ORDER BY id DESC
            LIMIT 10
            """
        ).fetchall()

    finally:

        close_db(db)


    # ============================================================
    # MD DASHBOARD
    # ============================================================

    return render_template(
        "md_dashboard.html",

        # Staff
        total_staff=total_staff,
        pending_staff=pending_staff,
        active_staff=active_staff,

        # Compatibility with the existing dashboard/template
        consultations=new_consultations,

        # Consultations
        total_consultations=total_consultations,
        new_consultations=new_consultations,
        in_progress_consultations=in_progress_consultations,
        closed_consultations=closed_consultations,
        unassigned_consultations=unassigned_consultations,

        # Recent data
        recent_consultations=recent_consultations,
        recent_staff=recent_staff
    )


# ============================================================
# MD STAFF
# ============================================================

@app.route("/md/staff")
@md_required
def md_staff():

    db = get_db()

    try:

        staff = db.execute(
            """
            SELECT *
            FROM staff
            ORDER BY id DESC
            """
        ).fetchall()

    finally:

        close_db(db)


    return render_template(
        "md_staff.html",
        staff=staff
    )


# ============================================================
# MD STAFF VIEW
# ============================================================

@app.route(
    "/md/staff/<int:staff_id>"
)
@md_required
def md_staff_view(
    staff_id
):

    db = get_db()

    try:

        staff = db.execute(
            """
            SELECT *
            FROM staff
            WHERE id = ?
            LIMIT 1
            """,
            (
                staff_id,
            )
        ).fetchone()

    finally:

        close_db(db)


    if not staff:

        flash(
            "Staff member not found.",
            "danger"
        )

        return redirect(
            url_for("md_staff")
        )


    return render_template(
        "md_staff_view.html",
        staff=staff
    )


# ============================================================
# MD STAFF PROFILE PHOTO
# ============================================================

@app.route("/md/staff/<int:staff_id>/photo")
@md_required
def md_staff_photo(staff_id):
    db = get_db()

    try:
        staff = db.execute(
            """
            SELECT profile_photo
            FROM staff
            WHERE id = ?
            LIMIT 1
            """,
            (staff_id,)
        ).fetchone()
    finally:
        close_db(db)

    # Staff does not exist or has no profile photo
    if not staff or not staff["profile_photo"]:
        abort(404)

    filename = secure_filename(staff["profile_photo"])

    if not filename:
        abort(404)

    photo_path = PROFILE_PHOTO_DIR / filename

    # Uploaded file does not exist
    if not photo_path.is_file():
        abort(404)

    return send_from_directory(
        PROFILE_PHOTO_DIR,
        filename
    )

# ============================================================
# MD STAFF ACTION
# ============================================================

@app.route(
    "/md/staff/<int:staff_id>/action",
    methods=["POST"]
)
@md_required
def md_staff_action(
    staff_id
):

    action = request.form.get(
        "action",
        ""
    ).strip().lower()


    if action not in (
        "approve",
        "reject",
        "disable",
        "activate",
    ):

        flash(
            "Invalid staff action.",
            "danger"
        )

        return redirect(
            url_for(
                "md_staff_view",
                staff_id=staff_id
            )
        )


    db = get_db()

    try:

        staff = db.execute(
            """
            SELECT *
            FROM staff
            WHERE id = ?
            LIMIT 1
            """,
            (
                staff_id,
            )
        ).fetchone()


        if not staff:

            flash(
                "Staff member not found.",
                "danger"
            )

            return redirect(
                url_for("md_staff")
            )


        new_status = {
            "approve": "Active",
            "reject": "Rejected",
            "disable": "Disabled",
            "activate": "Active",
        }[action]


        email = staff["email"]


        if (
            action in ("approve", "activate")
            and not email
        ):

            email = generate_staff_email(
                staff["first_name"],
                staff["last_name"],
                staff["staff_id"]
            )


        if action in (
            "approve",
            "activate"
        ):

            db.execute(
                """
                UPDATE staff
                SET
                    status = ?,
                    email = COALESCE(?, email),
                    approved_at = COALESCE(
                        approved_at,
                        ?
                    )

                WHERE id = ?
                """,
                (
                    new_status,
                    email,
                    utc_now(),
                    staff_id
                )
            )

        else:

            db.execute(
                """
                UPDATE staff
                SET status = ?
                WHERE id = ?
                """,
                (
                    new_status,
                    staff_id
                )
            )


        db.commit()

    finally:

        close_db(db)


    log_activity(
        "md",
        session["md_id"],
        f"staff_{action}",
        (
            f"MD performed {action} "
            f"on Staff ID {staff['staff_id']}."
        )
    )


    if action in (
        "approve",
        "activate"
    ):

        create_notification(
            staff_id,
            "Account Activated",
            (
                "Your Novera staff account "
                "has been activated."
            )
        )


        if email:

            send_email(
                email,
                "Novera Staff Account Activated",
                f"""
{COMPANY_NAME}

Your staff account has been activated.

Staff ID:
{staff["staff_id"]}

You can now log in to the staff portal.
"""
            )


    flash(
        "Staff status updated.",
        "success"
    )


    return redirect(
        url_for(
            "md_staff_view",
            staff_id=staff_id
        )
    )


# ============================================================
# ADMIN STAFF PROMOTION
# ============================================================

@app.route("/md/staff/<int:staff_id>/promote", methods=["POST"])
@md_required
def md_staff_promote(staff_id):
    new_position = request.form.get("position", "").strip()
    new_department = request.form.get("department", "").strip()
    if not new_position:
        flash("Please enter the new position.", "danger")
        return redirect(url_for("md_staff_view", staff_id=staff_id))

    db = get_db()
    try:
        staff = db.execute("SELECT * FROM staff WHERE id = ? LIMIT 1", (staff_id,)).fetchone()
        if not staff:
            flash("Staff member not found.", "danger")
            return redirect(url_for("md_staff"))
        old_position = staff["position"] or "Not assigned"
        old_department = staff["department"] or "Not assigned"
        if new_department:
            db.execute("UPDATE staff SET position = ?, department = ? WHERE id = ?", (new_position, new_department, staff_id))
        else:
            db.execute("UPDATE staff SET position = ? WHERE id = ?", (new_position, staff_id))
        db.commit()
    finally:
        close_db(db)

    log_activity("md", session["md_id"], "staff_promoted", f"Staff ID {staff['staff_id']} promoted. Position: {old_position} -> {new_position}. Department: {old_department} -> {new_department or old_department}.")
    create_notification(staff_id, "Position Updated", f"Your position has been updated to {new_position}." + (f" Department: {new_department}." if new_department else ""))
    if staff["email"]:
        send_email(staff["email"], f"{COMPANY_NAME} - Position Updated", f"Dear {staff['first_name']},\n\nYour position in the {COMPANY_NAME} staff portal has been updated.\n\nNew Position:\n{new_position}\n\n" + (f"Department:\n{new_department}\n\n" if new_department else "") + f"Your updated details will appear automatically in your staff portal.\n\nRegards,\n{COMPANY_NAME}\nPortal Administration\n")
    flash(f"{staff['first_name']} {staff['last_name']} has been promoted successfully.", "success")
    return redirect(url_for("md_staff_view", staff_id=staff_id))


# ============================================================
# MD CONSULTATIONS
# ============================================================

@app.route("/md/consultations")
@md_required
def md_consultations():

    db = get_db()

    try:

        consultations = db.execute(
            """
            SELECT
                c.*,

                s.first_name AS assigned_first_name,
                s.last_name AS assigned_last_name,
                s.staff_id AS assigned_staff_code,
                s.email AS assigned_staff_email,
                s.department AS assigned_department,
                s.position AS assigned_position,

                a.first_name AS assigned_by_first_name,
                a.last_name AS assigned_by_last_name,
                a.email AS assigned_by_email

            FROM consultations c

            LEFT JOIN staff s
                ON s.id = COALESCE(
                    c.assigned_staff_id,
                    c.assigned_to
                )

            LEFT JOIN admins a
                ON a.id = c.assigned_by

            ORDER BY c.id DESC
            """
        ).fetchall()

    finally:

        close_db(db)


    return render_template(
        "md_consultations.html",
        consultations=consultations
    )


# ============================================================
# MD CONSULTATION VIEW
# ============================================================

@app.route(
    "/md/consultations/<int:consultation_id>"
)
@md_required
def md_consultation_view(
    consultation_id
):

    db = get_db()

    try:

        consultation = db.execute(
            """
            SELECT
                c.*,

                s.first_name AS assigned_first_name,
                s.last_name AS assigned_last_name,
                s.staff_id AS assigned_staff_code,
                s.email AS assigned_staff_email,
                s.department AS assigned_department,
                s.position AS assigned_position,

                a.first_name AS assigned_by_first_name,
                a.last_name AS assigned_by_last_name,
                a.email AS assigned_by_email

            FROM consultations c

            LEFT JOIN staff s
                ON s.id = COALESCE(
                    c.assigned_staff_id,
                    c.assigned_to
                )

            LEFT JOIN admins a
                ON a.id = c.assigned_by

            WHERE c.id = ?

            LIMIT 1
            """,
            (
                consultation_id,
            )
        ).fetchone()

    finally:

        close_db(db)


    if not consultation:

        flash(
            "Consultation not found.",
            "danger"
        )

        return redirect(
            url_for("md_consultations")
        )


    return render_template(
        "md_consultation_view.html",
        consultation=consultation
    )


# ============================================================
# MD CONSULTATION MUTATION COMPATIBILITY ROUTES
# ============================================================

@app.route(
    "/md/consultations/<int:consultation_id>/assign",
    methods=["POST"]
)
@md_required
def md_consultation_assign(
    consultation_id
):

    flash(
        "Management consultation view is read-only.",
        "warning"
    )

    return redirect(
        url_for(
            "md_consultation_view",
            consultation_id=consultation_id
        )
    )


@app.route(
    "/md/consultations/<int:consultation_id>/unassign",
    methods=["POST"]
)
@md_required
def md_consultation_unassign(
    consultation_id
):

    flash(
        "Management consultation view is read-only.",
        "warning"
    )

    return redirect(
        url_for(
            "md_consultation_view",
            consultation_id=consultation_id
        )
    )


@app.route(
    "/md/consultations/<int:consultation_id>/status",
    methods=["POST"]
)
@md_required
def md_consultation_status(
    consultation_id
):

    flash(
        "Management consultation view is read-only.",
        "warning"
    )

    return redirect(
        url_for(
            "md_consultation_view",
            consultation_id=consultation_id
        )
    )


# ============================================================
# MD LOGOUT
# ============================================================

@app.route("/md/logout")
def md_logout():

    session.pop(
        "md_id",
        None
    )

    session.pop(
        "md_email",
        None
    )

    flash(
        "Management logged out.",
        "success"
    )

    return redirect(
        url_for("md_login")
    )


# ============================================================
# GENERIC 404
# ============================================================

@app.errorhandler(404)
def not_found(error):

    return (
        render_template(
            "404.html"
        )
        if (
            TEMPLATES_DIR / "404.html"
        ).exists()
        else "Page not found.",
        404
    )


# ============================================================
# GENERIC 500
# ============================================================

@app.errorhandler(500)
def internal_error(error):

    app.logger.exception(
        "Internal server error"
    )

    return (
        render_template(
            "500.html"
        )
        if (
            TEMPLATES_DIR / "500.html"
        ).exists()
        else "Internal server error.",
        500
    )


# ============================================================
# STARTUP
# ============================================================

try:

    init_database()

except Exception as startup_error:

    print()
    print("=" * 65)
    print("NOVERA DATABASE STARTUP ERROR")
    print("=" * 65)
    print(startup_error)
    print(f"Database: {DATABASE_PATH}")
    print("=" * 65)
    print()

    raise


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    print()
    print("=" * 65)
    print("NOVERA ENERGY & TECHNOLOGIES")
    print("BACKEND SERVER")
    print("=" * 65)
    print(f"Database : {DATABASE_PATH}")
    print(f"Templates: {TEMPLATES_DIR}")
    print(f"Website  : {INDEX_FILE}")
    print(f"Logo     : {LOGO_PATH}")
    print("=" * 65)
    print("Website:")
    print("http://127.0.0.1:5000/")
    print()
    print("Training Application:")
    print("http://127.0.0.1:5000/training/apply")
    print()
    print("Admin:")
    print("http://127.0.0.1:5000/admin/login")
    print()
    print("Staff:")
    print("http://127.0.0.1:5000/staff/login")
    print()
    print("MD:")
    print("http://127.0.0.1:5000/md/login")
    print("=" * 65)
    print()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
