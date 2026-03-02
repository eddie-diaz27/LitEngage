"""Create user accounts for authentication.

Seeds generic dev/test credentials:
- student / student123 (linked to Emma Johnson)
- librarian / librarian123 (no student profile)

Also creates accounts for the other 14 students (username=lowercase first name, password=password123).
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bcrypt

from backend.database.connection import SessionLocal
from backend.database.models import Student, UserAccount


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_accounts():
    db = SessionLocal()
    try:
        # Check if accounts already exist
        existing = db.query(UserAccount).count()
        if existing > 0:
            print(f"User accounts already exist ({existing} found). Skipping.")
            return

        accounts = []

        # 1. Generic student account - linked to Emma Johnson
        emma = db.query(Student).filter(Student.name == "Emma Johnson").first()
        if emma:
            accounts.append(UserAccount(
                username="student",
                hashed_password=hash_password("student123"),
                role="student",
                student_id=emma.id,
                display_name="Emma Johnson",
            ))
            print(f"  student / student123 -> {emma.name} (ID: {emma.id[:8]}...)")
        else:
            # Use the first student if Emma not found
            first_student = db.query(Student).first()
            if first_student:
                accounts.append(UserAccount(
                    username="student",
                    hashed_password=hash_password("student123"),
                    role="student",
                    student_id=first_student.id,
                    display_name=first_student.name,
                ))
                print(f"  student / student123 -> {first_student.name}")

        # 2. Generic librarian account
        accounts.append(UserAccount(
            username="librarian",
            hashed_password=hash_password("librarian123"),
            role="librarian",
            student_id=None,
            display_name="School Librarian",
        ))
        print("  librarian / librarian123 -> School Librarian")

        # 3. Accounts for all other students
        students = db.query(Student).all()
        for s in students:
            first_name = s.name.split()[0].lower()
            # Skip Emma since she already has the generic "student" account
            if s.name == "Emma Johnson":
                continue

            # Ensure unique username by checking for duplicates
            username = first_name
            existing_usernames = {a.username for a in accounts}
            if username in existing_usernames:
                username = f"{first_name}_{s.grade_level}"

            accounts.append(UserAccount(
                username=username,
                hashed_password=hash_password("password123"),
                role="student",
                student_id=s.id,
                display_name=s.name,
            ))

        # Insert all accounts
        for account in accounts:
            db.add(account)
        db.commit()

        print(f"\nCreated {len(accounts)} user accounts:")
        print(f"  - 1 generic student account (student/student123)")
        print(f"  - 1 generic librarian account (librarian/librarian123)")
        print(f"  - {len(accounts) - 2} individual student accounts (firstname/password123)")

    finally:
        db.close()


if __name__ == "__main__":
    print("Creating user accounts...\n")
    create_accounts()
    print("\nDone!")
