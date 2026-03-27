import os, sys
proj = 'C:/Users/Alonge Mohammed/Downloads/AI_Exam_System/AI_Exam_System'
os.chdir(proj)
sys.path.insert(0, proj)
from app import get_db, app
from werkzeug.security import check_password_hash

def test_login():
    with app.app_context():
        db = get_db()
        # Test admin login
        if (user := db.execute("SELECT * FROM users WHERE username='admin'").fetchone()):
            print(f"Admin user found: {user['username']}, role: {user['role']}")
            print(f"Password hash: {user['password'][:20]}...")
            # Test password
            test_pass = input("Enter admin password to test: ")
            if check_password_hash(user['password'], test_pass):
                print("✅ Password correct!")
            else:
                print("❌ Password incorrect!")
        else:
            print("Admin user not found!")

        # Test student
        if (user := db.execute("SELECT * FROM users WHERE username='student1'").fetchone()):
            print(f"Student user found: {user['username']}, role: {user['role']}")
            test_pass = input("Enter student password to test: ")
            if check_password_hash(user['password'], test_pass):
                print("✅ Student password correct!")
            else:
                print("❌ Student password incorrect!")
        else:
            print("Student user not found!")

if __name__ == "__main__":
    test_login()