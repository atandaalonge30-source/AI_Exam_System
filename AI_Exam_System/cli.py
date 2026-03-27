import os, sys
proj = 'C:/Users/Alonge Mohammed/Downloads/AI_Exam_System/AI_Exam_System'
os.chdir(proj)
sys.path.insert(0, proj)
from app import get_db, app
from werkzeug.security import check_password_hash

def cli_login():
    print("=== AI Exam System CLI ===")
    role = input("Login as (admin/student): ").strip().lower()
    username = input("Username: ").strip()
    password = input("Password: ").strip()

    with app.app_context():
        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username=? AND role=?",
            (username, role)
        ).fetchone()

        if user and check_password_hash(user['password'], password):
            print(f"✅ Welcome {user['full_name']} ({role})!")
            if role == 'admin':
                admin_menu(db, user)
            else:
                student_menu(db, user)
        else:
            print("❌ Invalid credentials!")

def admin_menu(db, user):
    while True:
        print("\n--- Admin Menu ---")
        print("1. View Students")
        print("2. View Exams")
        print("3. View Reports")
        print("4. Logout")
        choice = input("Choose: ").strip()

        if choice == '1':
            students = db.execute("SELECT * FROM users WHERE role='student'").fetchall()
            for s in students:
                print(f"- {s['full_name']} ({s['username']})")
        elif choice == '2':
            exams = db.execute("SELECT * FROM exams").fetchall()
            for e in exams:
                print(f"- {e['title']} ({e['course']}) - {'Active' if e['is_active'] else 'Inactive'}")
        elif choice == '3':
            sessions = db.execute("SELECT COUNT(*) as total FROM exam_sessions").fetchone()
            print(f"Total exam sessions: {sessions['total']}")
        elif choice == '4':
            break
        else:
            print("Invalid choice")

def student_menu(db, user):
    while True:
        print("\n--- Student Menu ---")
        print("1. View Available Exams")
        print("2. View My Results")
        print("3. Logout")
        choice = input("Choose: ").strip()

        if choice == '1':
            exams = db.execute("""
                SELECT e.* FROM exams e
                WHERE e.is_active = 1
            """).fetchall()
            for e in exams:
                completed = db.execute(
                    "SELECT id FROM exam_sessions WHERE exam_id=? AND student_id=? AND status='completed'",
                    (e['id'], user['id'])
                ).fetchone()
                status = "Completed" if completed else "Available"
                print(f"- {e['title']} ({e['course']}) - {status}")
        elif choice == '2':
            results = db.execute("""
                SELECT es.*, e.title FROM exam_sessions es
                JOIN exams e ON es.exam_id = e.id
                WHERE es.student_id = ? AND es.status = 'completed'
            """, (user['id'],)).fetchall()
            for r in results:
                print(f"- {r['title']}: {r['score']}/{r['total_questions']} ({r['score']/r['total_questions']*100:.1f}%)")
        elif choice == '3':
            break
        else:
            print("Invalid choice")

if __name__ == "__main__":
    cli_login()