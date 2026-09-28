import os
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import Flask, flash, g, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "database.db"
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "student-attendance-local-key")


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


@app.route("/students", methods=["GET", "POST"])
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
def delete_student(student_id):
    database = get_db()
    database.execute("DELETE FROM students WHERE id = ?", (student_id,))
    database.commit()
    flash("Student removed from the roster.", "success")
    return redirect(url_for("students"))


@app.route("/attendance", methods=["GET", "POST"])
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


init_db()


if __name__ == "__main__":
    app.run(debug=True)