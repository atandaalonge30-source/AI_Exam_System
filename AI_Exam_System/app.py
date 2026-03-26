import os
import sqlite3
import json
import base64
import io
from datetime import datetime
from functools import wraps
from flask import (Flask, render_template, request, redirect, url_for,
                   session, flash, jsonify, g, make_response)
import cv2
import numpy as np
from fpdf import FPDF

app = Flask(__name__)
app.secret_key = "exam_system_secret_2024"
DATABASE = "exam_system.db"

HAAR_CASCADE = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
face_cascade = cv2.CascadeClassifier(HAAR_CASCADE)


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                full_name TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS exams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                course TEXT NOT NULL,
                time_limit INTEGER NOT NULL,
                total_questions INTEGER NOT NULL,
                created_by INTEGER,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (created_by) REFERENCES users(id)
            );
            CREATE TABLE IF NOT EXISTS questions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                exam_id INTEGER NOT NULL,
                question_text TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                FOREIGN KEY (exam_id) REFERENCES exams(id)
            );
            CREATE TABLE IF NOT EXISTS exam_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id INTEGER NOT NULL,
                exam_id INTEGER NOT NULL,
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                score INTEGER DEFAULT 0,
                total_questions INTEGER DEFAULT 0,
                status TEXT DEFAULT 'in_progress',
                answers TEXT DEFAULT '{}',
                FOREIGN KEY (student_id) REFERENCES users(id),
                FOREIGN KEY (exam_id) REFERENCES exams(id)
            );
            CREATE TABLE IF NOT EXISTS proctoring_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                alert_type TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                details TEXT,
                FOREIGN KEY (session_id) REFERENCES exam_sessions(id)
            );
        """)
        existing = db.execute("SELECT COUNT(*) FROM users WHERE role='admin'").fetchone()[0]
        if existing == 0:
            db.execute(
                "INSERT INTO users (username, password, role, full_name, email) VALUES (?,?,?,?,?)",
                ("admin", "admin123", "admin", "System Administrator", "admin@examSystem.com")
            )
            db.execute(
                "INSERT INTO users (username, password, role, full_name, email) VALUES (?,?,?,?,?)",
                ("student1", "password", "student", "John Doe", "john@example.com")
            )
            sample_exam_id = db.execute(
                "INSERT INTO exams (title, description, course, time_limit, total_questions, created_by, is_active) VALUES (?,?,?,?,?,?,?)",
                ("Cyber Security Basics", "An introductory exam on cybersecurity fundamentals", "Cyber Security", 30, 5, 1, 1)
            ).lastrowid
            questions = [
                (sample_exam_id, "What does CIA stand for in cybersecurity?",
                 "Confidentiality, Integrity, Availability",
                 "Control, Integrity, Access",
                 "Confidentiality, Information, Access",
                 "Control, Information, Availability",
                 "A"),
                (sample_exam_id, "Which of the following is a type of malware?",
                 "Firewall", "Antivirus", "Ransomware", "VPN", "C"),
                (sample_exam_id, "What is phishing?",
                 "A type of encryption",
                 "A network protocol",
                 "A fraudulent attempt to steal sensitive info",
                 "A type of firewall", "C"),
                (sample_exam_id, "What does VPN stand for?",
                 "Virtual Private Network",
                 "Very Protected Node",
                 "Virtual Public Network",
                 "Verified Private Node", "A"),
                (sample_exam_id, "Which port does HTTPS use by default?",
                 "80", "21", "443", "8080", "C"),
            ]
            db.executemany(
                "INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_answer) VALUES (?,?,?,?,?,?,?)",
                questions
            )
            db.commit()


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Please log in.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            flash("Access denied. Admin only.", "danger")
            return redirect(url_for("student_dashboard"))
        return f(*args, **kwargs)
    return decorated


@app.route("/")
def index():
    if "user_id" in session:
        if session.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("student_dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        role = request.form.get("role", "student")
        db = get_db()
        if role == "admin":
            user = db.execute(
                "SELECT * FROM users WHERE username=? AND role='admin'",
                (username,)
            ).fetchone()
            if user:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["full_name"] = user["full_name"]
                session["role"] = "admin"
                flash(f"Welcome Admin {user['full_name']}!", "success")
                return redirect(url_for("admin_dashboard"))
            else:
                flash("Invalid admin credentials.", "danger")
        else:
            user = db.execute(
                "SELECT * FROM users WHERE username=? AND password=? AND role='student'",
                (username, password)
            ).fetchone()
            if user:
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["full_name"] = user["full_name"]
                session["role"] = "student"
                flash(f"Welcome {user['full_name']}!", "success")
                return redirect(url_for("student_dashboard"))
            else:
                flash("Invalid username or password.", "danger")
    return render_template("login.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        if not username or not password or not full_name:
            flash("All fields are required.", "danger")
            return render_template("register.html")
        db = get_db()
        existing = db.execute("SELECT id FROM users WHERE username=?", (username,)).fetchone()
        if existing:
            flash("Username already taken. Please choose another.", "danger")
            return render_template("register.html")
        db.execute(
            "INSERT INTO users (username, password, role, full_name, email) VALUES (?,?,?,?,?)",
            (username, password, "student", full_name, email)
        )
        db.commit()
        flash("Registration successful! You can now log in.", "success")
        return redirect(url_for("login"))
    return render_template("register.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully.", "info")
    return redirect(url_for("login"))


@app.route("/admin/dashboard")
@admin_required
def admin_dashboard():
    db = get_db()
    total_students = db.execute("SELECT COUNT(*) FROM users WHERE role='student'").fetchone()[0]
    total_exams = db.execute("SELECT COUNT(*) FROM exams").fetchone()[0]
    total_sessions = db.execute("SELECT COUNT(*) FROM exam_sessions WHERE status='completed'").fetchone()[0]
    total_alerts = db.execute("SELECT COUNT(*) FROM proctoring_logs").fetchone()[0]
    recent_sessions = db.execute("""
        SELECT es.id, u.full_name, e.title, es.score, es.total_questions, es.status, es.start_time
        FROM exam_sessions es
        JOIN users u ON es.student_id = u.id
        JOIN exams e ON es.exam_id = e.id
        ORDER BY es.start_time DESC LIMIT 10
    """).fetchall()
    return render_template("admin_dashboard.html",
                           total_students=total_students,
                           total_exams=total_exams,
                           total_sessions=total_sessions,
                           total_alerts=total_alerts,
                           recent_sessions=recent_sessions)


@app.route("/admin/exams")
@admin_required
def admin_exams():
    db = get_db()
    exams = db.execute("""
        SELECT e.*, COUNT(q.id) as question_count
        FROM exams e
        LEFT JOIN questions q ON e.id = q.exam_id
        GROUP BY e.id
        ORDER BY e.created_at DESC
    """).fetchall()
    return render_template("admin_exams.html", exams=exams)


@app.route("/admin/exam/create", methods=["GET", "POST"])
@admin_required
def create_exam():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        course = request.form.get("course", "").strip()
        time_limit = int(request.form.get("time_limit", 30))
        if not title or not course:
            flash("Title and course are required.", "danger")
            return render_template("create_exam.html")
        db = get_db()
        exam_id = db.execute(
            "INSERT INTO exams (title, description, course, time_limit, total_questions, created_by) VALUES (?,?,?,?,?,?)",
            (title, description, course, time_limit, 0, session["user_id"])
        ).lastrowid
        db.commit()
        flash("Exam created! Now add questions.", "success")
        return redirect(url_for("add_questions", exam_id=exam_id))
    return render_template("create_exam.html")


@app.route("/admin/exam/<int:exam_id>/questions", methods=["GET", "POST"])
@admin_required
def add_questions(exam_id):
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_id,)).fetchone()
    if not exam:
        flash("Exam not found.", "danger")
        return redirect(url_for("admin_exams"))
    if request.method == "POST":
        question_text = request.form.get("question_text", "").strip()
        option_a = request.form.get("option_a", "").strip()
        option_b = request.form.get("option_b", "").strip()
        option_c = request.form.get("option_c", "").strip()
        option_d = request.form.get("option_d", "").strip()
        correct_answer = request.form.get("correct_answer", "").strip()
        if not all([question_text, option_a, option_b, option_c, option_d, correct_answer]):
            flash("All fields are required.", "danger")
        else:
            db.execute(
                "INSERT INTO questions (exam_id, question_text, option_a, option_b, option_c, option_d, correct_answer) VALUES (?,?,?,?,?,?,?)",
                (exam_id, question_text, option_a, option_b, option_c, option_d, correct_answer)
            )
            count = db.execute("SELECT COUNT(*) FROM questions WHERE exam_id=?", (exam_id,)).fetchone()[0]
            db.execute("UPDATE exams SET total_questions=? WHERE id=?", (count, exam_id))
            db.commit()
            flash("Question added successfully!", "success")
    questions = db.execute("SELECT * FROM questions WHERE exam_id=?", (exam_id,)).fetchall()
    return render_template("add_questions.html", exam=exam, questions=questions)


@app.route("/admin/exam/<int:exam_id>/delete_question/<int:q_id>", methods=["POST"])
@admin_required
def delete_question(exam_id, q_id):
    db = get_db()
    db.execute("DELETE FROM questions WHERE id=? AND exam_id=?", (q_id, exam_id))
    count = db.execute("SELECT COUNT(*) FROM questions WHERE exam_id=?", (exam_id,)).fetchone()[0]
    db.execute("UPDATE exams SET total_questions=? WHERE id=?", (count, exam_id))
    db.commit()
    flash("Question deleted.", "info")
    return redirect(url_for("add_questions", exam_id=exam_id))


@app.route("/admin/exam/<int:exam_id>/toggle", methods=["POST"])
@admin_required
def toggle_exam(exam_id):
    db = get_db()
    exam = db.execute("SELECT is_active FROM exams WHERE id=?", (exam_id,)).fetchone()
    if exam:
        new_status = 0 if exam["is_active"] else 1
        db.execute("UPDATE exams SET is_active=? WHERE id=?", (new_status, exam_id))
        db.commit()
        status_text = "activated" if new_status else "deactivated"
        flash(f"Exam {status_text}.", "success")
    return redirect(url_for("admin_exams"))


@app.route("/admin/exam/<int:exam_id>/delete", methods=["POST"])
@admin_required
def delete_exam(exam_id):
    db = get_db()
    db.execute("DELETE FROM proctoring_logs WHERE session_id IN (SELECT id FROM exam_sessions WHERE exam_id=?)", (exam_id,))
    db.execute("DELETE FROM exam_sessions WHERE exam_id=?", (exam_id,))
    db.execute("DELETE FROM questions WHERE exam_id=?", (exam_id,))
    db.execute("DELETE FROM exams WHERE id=?", (exam_id,))
    db.commit()
    flash("Exam deleted.", "info")
    return redirect(url_for("admin_exams"))


@app.route("/admin/students")
@admin_required
def admin_students():
    db = get_db()
    students = db.execute("""
        SELECT u.*, COUNT(es.id) as exam_count
        FROM users u
        LEFT JOIN exam_sessions es ON u.id = es.student_id
        WHERE u.role='student'
        GROUP BY u.id
        ORDER BY u.created_at DESC
    """).fetchall()
    return render_template("admin_students.html", students=students)


@app.route("/admin/student/<int:student_id>/delete", methods=["POST"])
@admin_required
def delete_student(student_id):
    db = get_db()
    # Delete proctoring logs for student's sessions
    db.execute("DELETE FROM proctoring_logs WHERE session_id IN (SELECT id FROM exam_sessions WHERE student_id=?)", (student_id,))
    # Delete exam sessions
    db.execute("DELETE FROM exam_sessions WHERE student_id=?", (student_id,))
    # Delete user
    db.execute("DELETE FROM users WHERE id=? AND role='student'", (student_id,))
    db.commit()
    flash("Student deleted.", "info")
    return redirect(url_for("admin_students"))


@app.route("/admin/student/<int:student_id>/pdf")
@admin_required
def download_student_pdf(student_id):
    db = get_db()
    student = db.execute("SELECT * FROM users WHERE id=? AND role='student'", (student_id,)).fetchone()
    if not student:
        flash("Student not found.", "danger")
        return redirect(url_for("admin_students"))
    # Get exam results
    results = db.execute("""
        SELECT e.title, es.score, es.total_questions, es.start_time, es.end_time
        FROM exam_sessions es
        JOIN exams e ON es.exam_id = e.id
        WHERE es.student_id=? AND es.status='completed'
        ORDER BY es.end_time DESC
    """, (student_id,)).fetchall()
    # Generate PDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(200, 10, txt="Student Report", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.cell(200, 10, txt=f"Name: {student['full_name']}", ln=True)
    pdf.cell(200, 10, txt=f"Username: {student['username']}", ln=True)
    pdf.cell(200, 10, txt=f"Email: {student['email'] or 'N/A'}", ln=True)
    pdf.ln(10)
    pdf.set_font("Arial", "B", 14)
    pdf.cell(200, 10, txt="Exam Results:", ln=True)
    pdf.set_font("Arial", "", 12)
    if results:
        for r in results:
            pdf.cell(200, 10, txt=f"Exam: {r['title']}", ln=True)
            pdf.cell(200, 10, txt=f"Score: {r['score']}/{r['total_questions']}", ln=True)
            pdf.cell(200, 10, txt=f"Date: {r['end_time'][:10]}", ln=True)
            pdf.ln(5)
    else:
        pdf.cell(200, 10, txt="No exams completed.", ln=True)
    # Output PDF
    pdf_output = pdf.output(dest='S')
    if isinstance(pdf_output, str):
        pdf_bytes = pdf_output.encode('latin1')
    else:
        pdf_bytes = pdf_output
    response = make_response(pdf_bytes)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename={student["username"]}_report.pdf'
    return response


@app.route("/admin/reports")
@admin_required
def admin_reports():
    db = get_db()
    sessions = db.execute("""
        SELECT es.id, u.full_name, e.title, es.score, es.total_questions,
               es.status, es.start_time, es.end_time,
               COUNT(pl.id) as alert_count
        FROM exam_sessions es
        JOIN users u ON es.student_id = u.id
        JOIN exams e ON es.exam_id = e.id
        LEFT JOIN proctoring_logs pl ON es.id = pl.session_id
        GROUP BY es.id
        ORDER BY es.start_time DESC
    """).fetchall()
    return render_template("admin_reports.html", sessions=sessions)


@app.route("/admin/report/<int:session_id>")
@admin_required
def session_report(session_id):
    db = get_db()
    sess = db.execute("""
        SELECT es.*, u.full_name, u.username, e.title, e.course
        FROM exam_sessions es
        JOIN users u ON es.student_id = u.id
        JOIN exams e ON es.exam_id = e.id
        WHERE es.id=?
    """, (session_id,)).fetchone()
    if not sess:
        flash("Session not found.", "danger")
        return redirect(url_for("admin_reports"))
    logs = db.execute(
        "SELECT * FROM proctoring_logs WHERE session_id=? ORDER BY timestamp",
        (session_id,)
    ).fetchall()
    return render_template("session_report.html", sess=sess, logs=logs)


@app.route("/student/dashboard")
@login_required
def student_dashboard():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    db = get_db()
    available_exams = db.execute("""
        SELECT e.*,
            (SELECT COUNT(*) FROM exam_sessions es
             WHERE es.exam_id = e.id AND es.student_id = ? AND es.status='completed') as completed
        FROM exams e
        WHERE e.is_active = 1
        ORDER BY e.created_at DESC
    """, (session["user_id"],)).fetchall()
    my_results = db.execute("""
        SELECT es.*, e.title, e.course
        FROM exam_sessions es
        JOIN exams e ON es.exam_id = e.id
        WHERE es.student_id = ? AND es.status = 'completed'
        ORDER BY es.end_time DESC
    """, (session["user_id"],)).fetchall()
    return render_template("student_dashboard.html",
                           available_exams=available_exams,
                           my_results=my_results)


@app.route("/exam/<int:exam_id>/start")
@login_required
def start_exam(exam_id):
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    db = get_db()
    exam = db.execute("SELECT * FROM exams WHERE id=? AND is_active=1", (exam_id,)).fetchone()
    if not exam:
        flash("Exam not found or not active.", "danger")
        return redirect(url_for("student_dashboard"))
    questions = db.execute(
        "SELECT * FROM questions WHERE exam_id=? ORDER BY RANDOM()",
        (exam_id,)
    ).fetchall()
    if not questions:
        flash("This exam has no questions yet.", "warning")
        return redirect(url_for("student_dashboard"))
    existing = db.execute(
        "SELECT id FROM exam_sessions WHERE student_id=? AND exam_id=? AND status='completed'",
        (session["user_id"], exam_id)
    ).fetchone()
    if existing:
        flash("You have already completed this exam.", "info")
        return redirect(url_for("student_dashboard"))
    in_progress = db.execute(
        "SELECT id FROM exam_sessions WHERE student_id=? AND exam_id=? AND status='in_progress'",
        (session["user_id"], exam_id)
    ).fetchone()
    if in_progress:
        return redirect(url_for("take_exam", session_id=in_progress["id"]))
    new_session = db.execute(
        "INSERT INTO exam_sessions (student_id, exam_id, total_questions) VALUES (?,?,?)",
        (session["user_id"], exam_id, len(questions))
    ).lastrowid
    db.commit()
    return redirect(url_for("take_exam", session_id=new_session))


@app.route("/exam/session/<int:session_id>")
@login_required
def take_exam(session_id):
    db = get_db()
    exam_sess = db.execute(
        "SELECT * FROM exam_sessions WHERE id=? AND student_id=?",
        (session_id, session["user_id"])
    ).fetchone()
    if not exam_sess:
        flash("Exam session not found.", "danger")
        return redirect(url_for("student_dashboard"))
    if exam_sess["status"] == "completed":
        return redirect(url_for("exam_result", session_id=session_id))
    exam = db.execute("SELECT * FROM exams WHERE id=?", (exam_sess["exam_id"],)).fetchone()
    questions = db.execute(
        "SELECT * FROM questions WHERE exam_id=?",
        (exam_sess["exam_id"],)
    ).fetchall()
    return render_template("take_exam.html",
                           exam_sess=exam_sess,
                           exam=exam,
                           questions=questions)


@app.route("/exam/session/<int:session_id>/submit", methods=["POST"])
@login_required
def submit_exam(session_id):
    db = get_db()
    exam_sess = db.execute(
        "SELECT * FROM exam_sessions WHERE id=? AND student_id=? AND status='in_progress'",
        (session_id, session["user_id"])
    ).fetchone()
    if not exam_sess:
        flash("Session not found or already completed.", "warning")
        return redirect(url_for("student_dashboard"))
    answers = {}
    for key, value in request.form.items():
        if key.startswith("q_"):
            q_id = key[2:]
            answers[q_id] = value
    questions = db.execute(
        "SELECT * FROM questions WHERE exam_id=?", (exam_sess["exam_id"],)
    ).fetchall()
    score = 0
    for q in questions:
        submitted = answers.get(str(q["id"]), "")
        if submitted.upper() == q["correct_answer"].upper():
            score += 1
    db.execute(
        "UPDATE exam_sessions SET status='completed', end_time=CURRENT_TIMESTAMP, score=?, answers=? WHERE id=?",
        (score, json.dumps(answers), session_id)
    )
    db.commit()
    return redirect(url_for("exam_result", session_id=session_id))


@app.route("/exam/result/<int:session_id>")
@login_required
def exam_result(session_id):
    db = get_db()
    exam_sess = db.execute("""
        SELECT es.*, e.title, e.course, e.time_limit, u.full_name
        FROM exam_sessions es
        JOIN exams e ON es.exam_id = e.id
        JOIN users u ON es.student_id = u.id
        WHERE es.id=? AND es.student_id=?
    """, (session_id, session["user_id"])).fetchone()
    if not exam_sess:
        flash("Result not found.", "danger")
        return redirect(url_for("student_dashboard"))
    questions = db.execute(
        "SELECT * FROM questions WHERE exam_id=?", (exam_sess["exam_id"],)
    ).fetchall()
    answers = json.loads(exam_sess["answers"] or "{}")
    alerts = db.execute(
        "SELECT COUNT(*) FROM proctoring_logs WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    percentage = round((exam_sess["score"] / exam_sess["total_questions"]) * 100, 1) if exam_sess["total_questions"] > 0 else 0
    passed = percentage >= 50
    return render_template("exam_result.html",
                           exam_sess=exam_sess,
                           questions=questions,
                           answers=answers,
                           percentage=percentage,
                           passed=passed,
                           alerts=alerts)


@app.route("/api/proctoring/log", methods=["POST"])
@login_required
def log_proctoring_alert():
    data = request.get_json()
    session_id = data.get("session_id")
    alert_type = data.get("alert_type")
    details = data.get("details", "")
    if not session_id or not alert_type:
        return jsonify({"error": "Missing fields"}), 400
    db = get_db()
    db.execute(
        "INSERT INTO proctoring_logs (session_id, alert_type, details) VALUES (?,?,?)",
        (session_id, alert_type, details)
    )
    db.commit()
    return jsonify({"status": "logged"})


@app.route("/api/proctoring/analyze", methods=["POST"])
@login_required
def analyze_frame():
    data = request.get_json()
    frame_data = data.get("frame", "")
    if not frame_data:
        return jsonify({"faces": 0, "status": "no_frame"})
    try:
        if "," in frame_data:
            frame_data = frame_data.split(",")[1]
        img_bytes = base64.b64decode(frame_data)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({"faces": 0, "status": "decode_error"})
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50)
        )
        face_count = len(faces)
        if face_count == 0:
            status = "no_face"
        elif face_count == 1:
            status = "ok"
        else:
            status = "multiple_faces"
        return jsonify({"faces": face_count, "status": status})
    except Exception as e:
        return jsonify({"faces": 0, "status": "error", "message": str(e)})


if __name__ == "__main__":
    init_db()
    print("\n" + "="*60)
    print("  AI-Powered Examination & Proctoring System")
    print("="*60)
    print("  Server starting at: http://127.0.0.1:5000")
    print("  Admin Login  -> username: admin  | any password")
    print("  Student Demo -> username: student1 | password: password")
    print("="*60 + "\n")
    app.run(debug=True, host="0.0.0.0", port=5000)
