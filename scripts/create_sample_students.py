"""Create sample student profiles for testing and demo purposes."""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database.connection import SessionLocal
from backend.database import crud

# Reading level mapping by grade
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

SAMPLE_STUDENTS = [
    {
        "name": "Emma Johnson",
        "grade_level": 6,
        "preferences_json": {
            "favorite_genres": ["fantasy", "adventure"],
            "disliked_themes": [],
            "reading_pace": "moderate",
        },
    },
    {
        "name": "Liam Chen",
        "grade_level": 7,
        "preferences_json": {
            "favorite_genres": ["science-fiction", "dystopian"],
            "disliked_themes": ["romance"],
            "reading_pace": "fast",
        },
    },
    {
        "name": "Sophia Martinez",
        "grade_level": 8,
        "preferences_json": {
            "favorite_genres": ["mystery", "thriller"],
            "disliked_themes": [],
            "reading_pace": "moderate",
        },
    },
    {
        "name": "Noah Williams",
        "grade_level": 5,
        "preferences_json": {
            "favorite_genres": ["adventure", "humor"],
            "disliked_themes": ["horror"],
            "reading_pace": "slow",
        },
    },
    {
        "name": "Olivia Brown",
        "grade_level": 9,
        "preferences_json": {
            "favorite_genres": ["romance", "contemporary"],
            "disliked_themes": [],
            "reading_pace": "fast",
        },
    },
    {
        "name": "James Davis",
        "grade_level": 10,
        "preferences_json": {
            "favorite_genres": ["fantasy", "historical-fiction"],
            "disliked_themes": [],
            "reading_pace": "moderate",
        },
    },
    {
        "name": "Ava Wilson",
        "grade_level": 4,
        "preferences_json": {
            "favorite_genres": ["fantasy", "animals"],
            "disliked_themes": ["scary"],
            "reading_pace": "slow",
        },
    },
    {
        "name": "Lucas Taylor",
        "grade_level": 11,
        "preferences_json": {
            "favorite_genres": ["science-fiction", "thriller"],
            "disliked_themes": [],
            "reading_pace": "fast",
        },
    },
    {
        "name": "Mia Anderson",
        "grade_level": 6,
        "preferences_json": {
            "favorite_genres": ["realistic-fiction", "mystery"],
            "disliked_themes": [],
            "reading_pace": "moderate",
        },
    },
    {
        "name": "Ethan Thomas",
        "grade_level": 8,
        "preferences_json": {
            "favorite_genres": ["graphic-novels", "fantasy"],
            "disliked_themes": [],
            "reading_pace": "fast",
        },
    },
    {
        "name": "Isabella Garcia",
        "grade_level": 12,
        "preferences_json": {
            "favorite_genres": ["literary-fiction", "poetry"],
            "disliked_themes": [],
            "reading_pace": "slow",
        },
    },
    {
        "name": "Mason Lee",
        "grade_level": 7,
        "preferences_json": {
            "favorite_genres": ["adventure", "sports"],
            "disliked_themes": ["romance"],
            "reading_pace": "moderate",
        },
    },
    {
        "name": "Charlotte Kim",
        "grade_level": 9,
        "preferences_json": {
            "favorite_genres": ["fantasy", "romance"],
            "disliked_themes": [],
            "reading_pace": "fast",
        },
    },
    {
        "name": "Aiden Robinson",
        "grade_level": 3,
        "preferences_json": {
            "favorite_genres": ["adventure", "humor"],
            "disliked_themes": ["scary"],
            "reading_pace": "slow",
        },
    },
    {
        "name": "Harper Clark",
        "grade_level": 10,
        "preferences_json": {
            "favorite_genres": ["dystopian", "mystery"],
            "disliked_themes": [],
            "reading_pace": "moderate",
        },
    },
]


def create_sample_students():
    db = SessionLocal()

    try:
        created = 0
        for student_data in SAMPLE_STUDENTS:
            student_id = str(uuid.uuid4())
            grade = student_data["grade_level"]
            reading_level = GRADE_TO_READING_LEVEL.get(grade, "middle-school")

            crud.create_student(
                db,
                {
                    "id": student_id,
                    "name": student_data["name"],
                    "grade_level": grade,
                    "reading_level": reading_level,
                    "preferences_json": student_data["preferences_json"],
                },
            )
            created += 1
            print(
                f"  Created: {student_data['name']} "
                f"(Grade {grade}, {reading_level})"
            )

        print(f"\nCreated {created} sample students.")

    finally:
        db.close()


if __name__ == "__main__":
    create_sample_students()
