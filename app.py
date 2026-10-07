import os
import sqlite3
import hmac
import secrets
from datetime import date, timedelta
from functools import wraps
from pathlib import Path

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database.db"
app = Flask(__name__)
production = os.environ.get("APP_ENV") == "production"
secret_key = os.environ.get("SECRET_KEY")
if production and not secret_key:
    raise RuntimeError("Set SECRET_KEY in the hosting service environment.")
app.config["SECRET_KEY"] = secret_key or secrets.token_hex(32)
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = production
app.config["SETUP_TOKEN"] = os.environ.get("SETUP_TOKEN", "")
app.config["PASSWORD_RESET_TOKEN"] = os.environ.get("PASSWORD_RESET_TOKEN", "")


def login_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if not session.get("authenticated"):
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped_view


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()


def init_db():
    database = sqlite3.connect(DATABASE)
    database.execute("PRAGMA foreign_keys = ON")
    database.executescript(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            student_number TEXT NOT NULL UNIQUE,
            class_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL REFERENCES students(id) ON DELETE CASCADE,
            attendance_date TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('Present', 'Absent', 'Late', 'Excused')),
            UNIQUE(student_id, attendance_date)
        );
        CREATE TABLE IF NOT EXISTS admin_account (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        );
        """
    )
    if database.execute("SELECT COUNT(*) FROM students").fetchone()[0] == 0:
        database.executemany(
            "INSERT INTO students (name, student_number, class_name) VALUES (?, ?, ?)",
            [
                ("Olivia Chen", "ST-1042", "Grade 8 · A"),
                ("Noah Williams", "ST-1043", "Grade 8 · A"),
                ("Amara Okafor", "ST-1044", "Grade 8 · B"),
                ("Liam Patel", "ST-1045", "Grade 9 · A"),
                ("Sofia Martinez", "ST-1046", "Grade 9 · B"),
            ],
        )
    database.commit()
    database.close()


def valid_date(value, fallback):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return fallback


@app.route("/")
@login_required
def index():
    database = get_db()
    today = date.today().isoformat()
    total_students = database.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    today_rows = database.execute(
        "SELECT status, COUNT(*) AS total FROM attendance WHERE attendance_date = ? GROUP BY status",
        (today,),
    ).fetchall()
    today_counts = {row["status"]: row["total"] for row in today_rows}
    recorded = sum(today_counts.values())
    present = today_counts.get("Present", 0)
    recent = database.execute(
        """SELECT students.name, students.student_number, students.class_name,
                  attendance.status, attendance.attendance_date
           FROM attendance JOIN students ON students.id = attendance.student_id
           ORDER BY attendance.attendance_date DESC, attendance.id DESC LIMIT 6"""
    ).fetchall()
    week = []
    for offset in range(6, -1, -1):
        day = date.today() - timedelta(days=offset)
        count = database.execute(
            "SELECT COUNT(*) FROM attendance WHERE attendance_date = ? AND status = 'Present'",
            (day.isoformat(),),
        ).fetchone()[0]
        week.append({"label": day.strftime("%a"), "count": count})
    max_count = max((item["count"] for item in week), default=0)
    for item in week:
        item["height"] = round(item["count"] * 100 / max_count) if max_count else 4
    return render_template(
        "index.html",
        active="overview",
        today=date.today(),
        total_students=total_students,
        present=present,
        absent=today_counts.get("Absent", 0),
        recorded=recorded,
        attendance_rate=round(present * 100 / total_students) if total_students else 0,
        recent=recent,
        week=week,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authenticated"):
        return redirect(url_for("index"))

    database = get_db()
    account = database.execute(
        "SELECT username, password_hash FROM admin_account WHERE id = 1"
    ).fetchone()
    if account is None:
        return redirect(url_for("setup"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if hmac.compare_digest(username, account["username"]) and check_password_hash(account["password_hash"], password):
            session.clear()
            session["authenticated"] = True
            return redirect(url_for("index"))
        else:
            flash("Username or password is incorrect.", "error")

    return render_template("login.html")


@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if session.get("authenticated"):
        return redirect(url_for("index"))
    if not production and request.remote_addr not in {"127.0.0.1", "::1"}:
        abort(403)

    database = get_db()
    account_exists = database.execute(
        "SELECT 1 FROM admin_account WHERE id = 1"
    ).fetchone()
    if account_exists is None:
        return redirect(url_for("setup"))

    reset_token = app.config["PASSWORD_RESET_TOKEN"]
    if request.method == "POST":
        submitted_token = request.form.get("reset_token", "")
        password = request.form.get("password", "")
        password_confirmation = request.form.get("password_confirmation", "")
        if production and not reset_token:
            flash("Password reset is not configured. Contact your administrator.", "error")
        elif production and not hmac.compare_digest(submitted_token, reset_token):
            flash("The recovery code is incorrect.", "error")
        elif len(password) < 12:
            flash("Choose a password with at least 12 characters.", "error")
        elif password != password_confirmation:
            flash("The passwords do not match.", "error")
        else:
            database.execute(
                "UPDATE admin_account SET password_hash = ? WHERE id = 1",
                (generate_password_hash(password),),
            )
            database.commit()
            flash("Password updated. You can now sign in.", "success")
            return redirect(url_for("login"))

    return render_template(
        "forgot_password.html",
        reset_enabled=not production or bool(reset_token),
        reset_token_required=production,
    )


@app.route("/setup", methods=["GET", "POST"])
def setup():
    database = get_db()
    account_exists = database.execute(
        "SELECT 1 FROM admin_account WHERE id = 1"
    ).fetchone()
    if account_exists:
        return redirect(url_for("login"))

    if request.method == "POST":
        setup_token = request.form.get("setup_token", "")
        required_token = app.config["SETUP_TOKEN"]
        if production and not required_token:
            flash("Administrator setup is not enabled on this server yet.", "error")
        elif production and not hmac.compare_digest(setup_token, required_token):
            flash("The setup code is incorrect.", "error")
        else:
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            password_confirmation = request.form.get("password_confirmation", "")
            if not 3 <= len(username) <= 40:
                flash("Choose a username between 3 and 40 characters.", "error")
            elif len(password) < 12:
                flash("Choose a password with at least 12 characters.", "error")
            elif password != password_confirmation:
                flash("The passwords do not match.", "error")
            else:
                try:
                    database.execute(
                        "INSERT INTO admin_account (id, username, password_hash) VALUES (1, ?, ?)",
                        (username, generate_password_hash(password)),
                    )
                    database.commit()
                    flash("Administrator account created. You can now sign in.", "success")
                    return redirect(url_for("login"))
                except sqlite3.IntegrityError:
                    database.rollback()
                    flash("An administrator account has already been created.", "error")

    return render_template("setup.html", setup_token_required=production)


@app.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/students", methods=["GET", "POST"])
@login_required
def students():
    database = get_db()
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        student_number = request.form.get("student_number", "").strip()
        class_name = request.form.get("class_name", "").strip()
        if not all((name, student_number, class_name)):
            flash("Please complete all student details.", "error")
        else:
            try:
                database.execute(
                    "INSERT INTO students (name, student_number, class_name) VALUES (?, ?, ?)",
                    (name, student_number, class_name),
                )
                database.commit()
                flash(f"{name} has been added to your roster.", "success")
            except sqlite3.IntegrityError:
                flash("That student number is already in use.", "error")
        return redirect(url_for("students"))

    roster = database.execute(
        """SELECT students.*,
                  SUM(CASE WHEN attendance.status = 'Present' THEN 1 ELSE 0 END) AS present_days,
                  COUNT(attendance.id) AS recorded_days
           FROM students LEFT JOIN attendance ON attendance.student_id = students.id
           GROUP BY students.id ORDER BY students.name COLLATE NOCASE"""
    ).fetchall()
    return render_template("students.html", active="students", students=roster)


@app.post("/students/<int:student_id>/delete")
@login_required
def delete_student(student_id):
    database = get_db()
    database.execute("DELETE FROM students WHERE id = ?", (student_id,))
    database.commit()
    flash("Student removed from the roster.", "success")
    return redirect(url_for("students"))


@app.post("/students/<int:student_id>/edit")
@login_required
def edit_student(student_id):
    name = request.form.get("name", "").strip()
    if not name or len(name) > 100:
        flash("Enter a name between 1 and 100 characters.", "error")
        return redirect(url_for("students"))

    database = get_db()
    result = database.execute(
        "UPDATE students SET name = ? WHERE id = ?", (name, student_id)
    )
    database.commit()
    if result.rowcount:
        flash("Student name updated.", "success")
    else:
        flash("Student could not be found.", "error")
    return redirect(url_for("students"))


@app.route("/attendance", methods=["GET", "POST"])
@login_required
def attendance():
    database = get_db()
    selected_date = valid_date(request.values.get("date"), date.today()).isoformat()
    if request.method == "POST":
        selected_date = valid_date(request.form.get("attendance_date"), date.today()).isoformat()
        students_on_day = database.execute("SELECT id FROM students").fetchall()
        for student in students_on_day:
            status = request.form.get(f"status_{student['id']}")
            if status in {"Present", "Absent", "Late", "Excused"}:
                database.execute(
                    """INSERT INTO attendance (student_id, attendance_date, status) VALUES (?, ?, ?)
                       ON CONFLICT(student_id, attendance_date) DO UPDATE SET status = excluded.status""",
                    (student["id"], selected_date, status),
                )
        database.commit()
        flash("Attendance has been saved.", "success")
        return redirect(url_for("attendance", date=selected_date))

    roster = database.execute(
        """SELECT students.id, students.name, students.student_number, students.class_name,
                  attendance.status
           FROM students LEFT JOIN attendance
             ON attendance.student_id = students.id AND attendance.attendance_date = ?
           ORDER BY students.name COLLATE NOCASE""",
        (selected_date,),
    ).fetchall()
    counts = {"Present": 0, "Absent": 0, "Late": 0, "Excused": 0, "Unmarked": 0}
    for student in roster:
        counts[student["status"] or "Unmarked"] += 1
    return render_template(
        "attendance.html", active="attendance", students=roster,
        selected_date=selected_date, counts=counts,
    )


@app.route("/report")
@login_required
def report():
    today = date.today()
    start_date = valid_date(request.args.get("from"), today.replace(day=1)).isoformat()
    end_date = valid_date(request.args.get("to"), today).isoformat()
    if start_date > end_date:
        start_date, end_date = end_date, start_date
    database = get_db()
    summary = database.execute(
        """SELECT COUNT(*) AS total,
                  SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present,
                  SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS absent,
                  SUM(CASE WHEN status = 'Late' THEN 1 ELSE 0 END) AS late
           FROM attendance WHERE attendance_date BETWEEN ? AND ?""",
        (start_date, end_date),
    ).fetchone()
    by_student = database.execute(
        """SELECT students.name, students.student_number, students.class_name,
                  COUNT(attendance.id) AS days_recorded,
                  SUM(CASE WHEN attendance.status = 'Present' THEN 1 ELSE 0 END) AS present_days,
                  SUM(CASE WHEN attendance.status = 'Absent' THEN 1 ELSE 0 END) AS absent_days,
                  SUM(CASE WHEN attendance.status = 'Late' THEN 1 ELSE 0 END) AS late_days
           FROM students LEFT JOIN attendance
             ON attendance.student_id = students.id
             AND attendance.attendance_date BETWEEN ? AND ?
           GROUP BY students.id ORDER BY students.name COLLATE NOCASE""",
        (start_date, end_date),
    ).fetchall()
    total = summary["total"] or 0
    present = summary["present"] or 0
    return render_template(
        "report.html", active="report", start_date=start_date, end_date=end_date,
        summary=summary, by_student=by_student,
        attendance_rate=round(present * 100 / total) if total else 0,
    )


@app.route("/database")
@login_required
def database_view():
    database = get_db()
    tables = database.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    table_names = [t["name"] for t in tables]

    selected_table = request.args.get("table", table_names[0] if table_names else "")
    if selected_table not in table_names and table_names:
        selected_table = table_names[0]

    columns = []
    rows = []
    counts = {}
    for name in table_names:
        counts[name] = database.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]

    if selected_table:
        col_info = database.execute(f"PRAGMA table_info({selected_table})").fetchall()
        columns = [c["name"] for c in col_info]
        rows = database.execute(f"SELECT * FROM {selected_table} LIMIT 100").fetchall()

    return render_template(
        "database.html",
        active="database",
        table_names=table_names,
        selected_table=selected_table,
        columns=columns,
        rows=rows,
        counts=counts,
    )


init_db()


if __name__ == "__main__":
    app.run(debug=True)