"""Create 50 additional student profiles for realistic review distribution.

These students don't get UserAccount records — they represent other students
at the school who have read and reviewed books.
"""

import os
import random
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.connection import SessionLocal
from backend.database.models import Student

GRADE_TO_READING_LEVEL = {
    3: "elementary",
    4: "elementary",
    5: "elementary",
    6: "middle-school",
    7: "middle-school",
    8: "middle-school",
    9: "high-school",
    10: "high-school",
    11: "high-school",
    12: "high-school",
}

FIRST_NAMES = [
    "Zoe", "Ryan", "Lily", "Jack", "Chloe", "Dylan", "Grace", "Owen",
    "Ella", "Caleb", "Aria", "Nathan", "Layla", "Leo", "Nora",
    "Henry", "Scarlett", "Samuel", "Penelope", "Isaac",
    "Victoria", "Gabriel", "Stella", "Julian", "Hazel",
    "Mateo", "Violet", "Daniel", "Aurora", "Sebastian",
    "Savannah", "Elijah", "Audrey", "Levi", "Brooklyn",
    "Carter", "Paisley", "Jayden", "Skylar", "Lincoln",
    "Maya", "Asher", "Bella", "Thomas", "Claire",
    "Finn", "Lucy", "Miles", "Riley", "Xavier",
]

LAST_NAMES = [
    "Nguyen", "Patel", "O'Brien", "Rivera", "Yamamoto", "Fischer",
    "Singh", "Santos", "Ahmed", "Kowalski", "Hansen", "Nakamura",
    "Morales", "Thompson", "Volkov", "Reyes", "Murphy", "Suzuki",
    "Diaz", "Bennett", "Johansson", "Torres", "Price", "Hoffman",
    "Gutierrez", "Foster", "Tanaka", "Mitchell", "Cruz", "Sullivan",
    "Park", "Reed", "Ivanov", "White", "Flores", "Gray",
    "Woods", "Barnes", "Ross", "Campbell", "Stewart", "Morgan",
    "Bell", "Howard", "Ward", "Cox", "Perry", "Long",
    "Hughes", "Butler",
]

GENRE_POOLS = [
    ["fantasy", "adventure"],
    ["science-fiction", "dystopian"],
    ["mystery", "thriller"],
    ["romance", "contemporary"],
    ["historical-fiction", "adventure"],
    ["humor", "realistic-fiction"],
    ["horror", "thriller"],
    ["graphic-novels", "fantasy"],
    ["literary-fiction", "poetry"],
    ["adventure", "sports"],
]


def create_additional_students():
    db = SessionLocal()

    try:
        existing_names = {s.name for s in db.query(Student.name).all()}

        created = 0
        for i in range(50):
            name = f"{FIRST_NAMES[i]} {LAST_NAMES[i]}"

            if name in existing_names:
                print(f"  Skipping (exists): {name}")
                continue

            grade = random.randint(3, 12)
            reading_level = GRADE_TO_READING_LEVEL[grade]
            genres = random.choice(GENRE_POOLS)

            student = Student(
                id=str(uuid.uuid4()),
                name=name,
                grade_level=grade,
                reading_level=reading_level,
                preferences_json={
                    "favorite_genres": genres,
                    "disliked_themes": [],
                    "reading_pace": random.choice(["slow", "moderate", "fast"]),
                },
            )
            db.add(student)
            created += 1

        db.commit()
        total = db.query(Student).count()
        print(f"Created {created} additional students. Total students: {total}")

    finally:
        db.close()


if __name__ == "__main__":
    create_additional_students()
