"""Demo script: inject problematic reviews for moderation demo, or revert them.

Usage:
    python scripts/demo_problematic_reviews.py          # Inject problematic reviews
    python scripts/demo_problematic_reviews.py --revert  # Restore originals
"""

import json
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from backend.database.connection import SessionLocal
from backend.database.models import StudentReview

BACKUP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data",
    "demo_review_backup.json",
)

# Problematic replacement texts — realistic but PG, each targets a different
# moderation category so the AI scanner flags them with different labels.
REPLACEMENTS = [
    {
        "target_flag": "toxicity / bullying",
        "text": (
            "This book is terrible. Anyone who actually likes this must be "
            "really stupid. The main character is such a loser and honestly "
            "if you enjoy reading this garbage you probably have no friends."
        ),
    },
    {
        "target_flag": "major spoiler",
        "text": (
            "SPOILER ALERT: The main character dies at the end!! His best "
            "friend was the traitor the whole time and the kingdom falls. "
            "The secret weapon was hidden in the library. Don't bother reading "
            "it now that you know everything."
        ),
    },
    {
        "target_flag": "off-topic",
        "text": (
            "I didn't actually read this book. Anyway, does anyone want to "
            "trade Pokemon cards at lunch tomorrow? I have a holographic "
            "Charizard. Also my TikTok is @coolkid99 follow me for follow. "
            "DM me on Instagram."
        ),
    },
    {
        "target_flag": "toxicity / harassment",
        "text": (
            "I hate this author so much. Their writing is complete trash and "
            "they should be embarrassed. Mrs. Rodriguez made us read this and "
            "she has the worst taste in books ever. Worst teacher AND worst book."
        ),
    },
    {
        "target_flag": "age-inappropriate",
        "text": (
            "This book was way too dark. There was a lot of really graphic "
            "violence and the characters kept talking about doing drugs and "
            "drinking. I don't think this should be in a school library at all. "
            "Some scenes made me really uncomfortable."
        ),
    },
    {
        "target_flag": "bullying / personal attack",
        "text": (
            "I only read this because Jayden from my class said it was good "
            "and I wanted to prove him wrong. Jayden always picks dumb books. "
            "Nobody in our reading group likes his suggestions. He should stop "
            "trying to act smart."
        ),
    },
    {
        "target_flag": "off-topic / self-promotion",
        "text": (
            "Check out my YouTube channel where I review books way better "
            "than this library system does. Link in my bio. Subscribe and "
            "hit the bell. Also selling candy in the cafeteria, $2 each. "
            "This book was whatever I guess."
        ),
    },
    {
        "target_flag": "spoiler + mean-spirited",
        "text": (
            "The ending is so predictable — obviously the girl chooses the "
            "nice guy and the bully gets expelled. If you couldn't figure "
            "that out from chapter one you probably can't read very well. "
            "The twist about the teacher being her mom was obvious too."
        ),
    },
]


def inject(db: Session):
    """Pick 8 clean reviews, back them up, replace with problematic text."""
    # Get clean, approved reviews with text — spread across different students
    reviews = (
        db.query(StudentReview)
        .filter(
            StudentReview.moderation_status == "clean",
            StudentReview.is_approved == True,
            StudentReview.review_text.isnot(None),
        )
        .order_by(StudentReview.id.desc())
        .limit(200)
        .all()
    )

    if len(reviews) < len(REPLACEMENTS):
        print(f"Not enough clean reviews ({len(reviews)}). Need {len(REPLACEMENTS)}.")
        return

    # Pick reviews from different students for variety
    seen_students = set()
    selected = []
    for r in reviews:
        if r.student_id not in seen_students and len(selected) < len(REPLACEMENTS):
            selected.append(r)
            seen_students.add(r.student_id)
    # Fill remaining if not enough unique students
    for r in reviews:
        if r not in selected and len(selected) < len(REPLACEMENTS):
            selected.append(r)

    # Back up originals
    backup = []
    now = datetime.utcnow()

    for i, review in enumerate(selected):
        backup.append({
            "review_id": review.id,
            "original_text": review.review_text,
            "original_created_at": review.created_at.isoformat() if review.created_at else None,
            "original_moderation_status": review.moderation_status,
            "original_moderation_flags": review.moderation_flags,
            "original_moderation_reason": review.moderation_reason,
            "original_is_approved": review.is_approved,
        })

        # Replace with problematic text
        review.review_text = REPLACEMENTS[i]["text"]
        review.moderation_status = "pending"
        review.moderation_flags = None
        review.moderation_reason = None
        review.moderated_at = None
        # Bump created_at to now so they appear at the top of "recent reviews"
        review.created_at = now - timedelta(minutes=len(REPLACEMENTS) - i)
        # Keep is_approved=True so they appear visible until the scan flags them

        student_name = review.student.name if review.student else "?"
        book_title = review.book.title if review.book else "?"
        print(f"  [{REPLACEMENTS[i]['target_flag']}]")
        print(f"    Review #{review.id}: {student_name} -> \"{book_title}\"")
        print(f"    Text: \"{REPLACEMENTS[i]['text'][:70]}...\"")
        print()

    # Save backup
    with open(BACKUP_PATH, "w") as f:
        json.dump(backup, f, indent=2)

    db.commit()
    print(f"Injected {len(selected)} problematic reviews.")
    print(f"Backup saved to: {BACKUP_PATH}")
    print()
    print("Now go to Book Management > Review Moderation and click 'Scan All Pending'!")


def revert(db: Session):
    """Restore reviews from backup."""
    if not os.path.exists(BACKUP_PATH):
        print(f"No backup found at {BACKUP_PATH}. Nothing to revert.")
        return

    with open(BACKUP_PATH) as f:
        backup = json.load(f)

    for entry in backup:
        review = db.query(StudentReview).filter(StudentReview.id == entry["review_id"]).first()
        if review:
            review.review_text = entry["original_text"]
            review.moderation_status = entry["original_moderation_status"]
            review.moderation_flags = entry["original_moderation_flags"]
            review.moderation_reason = entry["original_moderation_reason"]
            review.is_approved = entry["original_is_approved"]
            if entry.get("original_created_at"):
                review.created_at = datetime.fromisoformat(entry["original_created_at"])
            review.moderated_at = None
            print(f"  Restored review #{review.id}")
        else:
            print(f"  Review #{entry['review_id']} not found (skipped)")

    db.commit()
    os.remove(BACKUP_PATH)
    print(f"\nReverted {len(backup)} reviews to original state.")
    print("Backup file removed.")


def main():
    revert_mode = "--revert" in sys.argv

    db = SessionLocal()
    try:
        if revert_mode:
            print("Reverting problematic reviews...\n")
            revert(db)
        else:
            # Check if already injected
            if os.path.exists(BACKUP_PATH):
                print("Problematic reviews already injected!")
                print("Run with --revert first, or delete the backup file.")
                return
            print("Injecting problematic reviews for moderation demo...\n")
            inject(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
