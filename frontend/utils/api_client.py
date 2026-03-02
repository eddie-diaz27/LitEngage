"""HTTP client for communicating with the FastAPI backend."""

import os

import httpx


BACKEND_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000")


class APIClient:
    """Synchronous API client for Streamlit (runs in sync context)."""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = f"{base_url}/api"

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=120.0)

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def login(self, username: str, password: str) -> dict:
        with self._client() as client:
            resp = client.post(
                "/auth/login",
                json={"username": username, "password": password},
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def create_session(self, student_id: str) -> dict:
        with self._client() as client:
            resp = client.post(
                "/chat/sessions", json={"student_id": student_id}
            )
            resp.raise_for_status()
            return resp.json()

    def send_message(
        self, student_id: str, session_id: str, message: str
    ) -> dict:
        with self._client() as client:
            resp = client.post(
                "/chat/message",
                json={
                    "student_id": student_id,
                    "session_id": session_id,
                    "message": message,
                },
            )
            resp.raise_for_status()
            return resp.json()

    def send_librarian_message(self, message: str, session_id: str = None) -> dict:
        with self._client() as client:
            payload = {"message": message}
            if session_id:
                payload["session_id"] = session_id
            resp = client.post("/chat/message/librarian", json=payload)
            resp.raise_for_status()
            return resp.json()

    def get_session(self, session_id: int) -> dict:
        with self._client() as client:
            resp = client.get(f"/chat/sessions/{session_id}")
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Students
    # ------------------------------------------------------------------

    def get_students(self) -> list:
        with self._client() as client:
            resp = client.get("/students/")
            resp.raise_for_status()
            return resp.json()

    def get_student(self, student_id: str) -> dict:
        with self._client() as client:
            resp = client.get(f"/students/{student_id}")
            resp.raise_for_status()
            return resp.json()

    def get_student_profile(self, student_id: str) -> dict:
        with self._client() as client:
            resp = client.get(f"/students/{student_id}/profile")
            resp.raise_for_status()
            return resp.json()

    def get_reading_history(self, student_id: str, limit: int = 50) -> list:
        with self._client() as client:
            resp = client.get(f"/students/{student_id}/history", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()

    def add_to_reading_list(self, student_id: str, book_id: str, status: str = "wishlist") -> dict:
        with self._client() as client:
            resp = client.post(
                f"/students/{student_id}/history",
                json={"book_id": book_id, "status": status},
            )
            resp.raise_for_status()
            return resp.json()

    def update_reading_status(self, student_id: str, entry_id: int, status: str = None, rating: int = None) -> dict:
        with self._client() as client:
            payload = {}
            if status:
                payload["status"] = status
            if rating is not None:
                payload["rating"] = rating
            resp = client.put(f"/students/{student_id}/history/{entry_id}", json=payload)
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Books
    # ------------------------------------------------------------------

    def get_books(
        self,
        skip: int = 0,
        limit: int = 20,
        reading_level: str = None,
        min_rating: float = None,
        sort_by: str = "ratings_count",
        sort_order: str = "desc",
    ) -> dict:
        params = {"skip": skip, "limit": limit, "sort_by": sort_by, "sort_order": sort_order}
        if reading_level:
            params["reading_level"] = reading_level
        if min_rating:
            params["min_rating"] = min_rating

        with self._client() as client:
            resp = client.get("/books/", params=params)
            resp.raise_for_status()
            return resp.json()

    def get_book(self, book_id: str) -> dict:
        with self._client() as client:
            resp = client.get(f"/books/{book_id}")
            resp.raise_for_status()
            return resp.json()

    def get_trending_books(self, limit: int = 5) -> list:
        with self._client() as client:
            resp = client.get("/books/trending", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()

    def get_book_stats(self, book_id: str) -> dict:
        with self._client() as client:
            resp = client.get(f"/books/{book_id}/stats")
            resp.raise_for_status()
            return resp.json()

    def title_search_books(self, q: str = "", limit: int = 20) -> list:
        with self._client() as client:
            resp = client.get("/books/title-search", params={"q": q, "limit": limit})
            resp.raise_for_status()
            return resp.json()

    def search_books(self, query: str, reading_level: str = None, max_results: int = 10) -> list:
        payload = {"query": query, "max_results": max_results}
        if reading_level:
            payload["reading_level"] = reading_level

        with self._client() as client:
            resp = client.post("/books/search", json=payload)
            resp.raise_for_status()
            return resp.json()

    def create_book(self, book_data: dict) -> dict:
        with self._client() as client:
            resp = client.post("/books/", json=book_data)
            resp.raise_for_status()
            return resp.json()

    def update_book(self, book_id: str, book_data: dict) -> dict:
        with self._client() as client:
            resp = client.put(f"/books/{book_id}", json=book_data)
            resp.raise_for_status()
            return resp.json()

    def delete_book(self, book_id: str) -> dict:
        with self._client() as client:
            resp = client.delete(f"/books/{book_id}")
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Reviews
    # ------------------------------------------------------------------

    def get_recent_reviews(self, limit: int = 50, include_hidden: bool = True) -> list:
        with self._client() as client:
            resp = client.get(
                "/reviews/recent",
                params={"limit": limit, "include_hidden": include_hidden},
            )
            resp.raise_for_status()
            return resp.json()

    def create_review(self, student_id: str, book_id: str, rating: int, review_text: str = None) -> dict:
        with self._client() as client:
            payload = {"student_id": student_id, "book_id": book_id, "rating": rating}
            if review_text:
                payload["review_text"] = review_text
            resp = client.post("/reviews/", json=payload)
            resp.raise_for_status()
            return resp.json()

    def get_book_reviews(self, book_id: str) -> list:
        with self._client() as client:
            resp = client.get(f"/reviews/book/{book_id}")
            resp.raise_for_status()
            return resp.json()

    def get_student_reviews(self, student_id: str) -> list:
        with self._client() as client:
            resp = client.get(f"/reviews/student/{student_id}")
            resp.raise_for_status()
            return resp.json()

    def moderate_review(self, review_id: int, is_approved: bool) -> dict:
        with self._client() as client:
            resp = client.put(f"/reviews/{review_id}/moderate", json={"is_approved": is_approved})
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Gamification
    # ------------------------------------------------------------------

    def get_leaderboard(self, limit: int = 20) -> list:
        with self._client() as client:
            resp = client.get("/gamification/leaderboard", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()

    def get_badges(self, student_id: str) -> list:
        with self._client() as client:
            resp = client.get(f"/gamification/student/{student_id}/badges")
            resp.raise_for_status()
            return resp.json()

    def get_streak(self, student_id: str) -> dict:
        with self._client() as client:
            resp = client.get(f"/gamification/student/{student_id}/streak")
            resp.raise_for_status()
            return resp.json()

    def get_reading_goal(self, student_id: str) -> dict:
        with self._client() as client:
            resp = client.get(f"/gamification/student/{student_id}/goal")
            resp.raise_for_status()
            return resp.json()

    def set_reading_goal(self, student_id: str, target_books: int) -> dict:
        with self._client() as client:
            resp = client.post(
                f"/gamification/student/{student_id}/goal",
                json={"target_books": target_books},
            )
            resp.raise_for_status()
            return resp.json()

    def check_badges(self, student_id: str) -> dict:
        with self._client() as client:
            resp = client.post(f"/gamification/student/{student_id}/check-badges")
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    def get_recent_recommendations(self, limit: int = 20) -> list:
        with self._client() as client:
            resp = client.get(
                "/recommendations/recent", params={"limit": limit}
            )
            resp.raise_for_status()
            return resp.json()

    def submit_feedback(self, rec_id: int, feedback: str) -> dict:
        with self._client() as client:
            resp = client.post(
                f"/recommendations/{rec_id}/feedback",
                json={"feedback": feedback},
            )
            resp.raise_for_status()
            return resp.json()

    def get_analytics(self) -> dict:
        with self._client() as client:
            resp = client.get("/recommendations/analytics")
            resp.raise_for_status()
            return resp.json()

    def get_auto_recommendations(self, student_id: str, count: int = 3, refresh: bool = False) -> dict:
        with self._client() as client:
            resp = client.post(
                f"/recommendations/auto/{student_id}",
                params={"count": count, "refresh": refresh},
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Admin
    # ------------------------------------------------------------------

    def get_token_usage(self, days: int = 30) -> dict:
        with self._client() as client:
            resp = client.get("/admin/token-usage", params={"days": days})
            resp.raise_for_status()
            return resp.json()

    def get_alerts(self) -> list:
        with self._client() as client:
            resp = client.get("/admin/alerts")
            resp.raise_for_status()
            return resp.json()

    def get_genre_stats(self) -> list:
        with self._client() as client:
            resp = client.get("/admin/stats/genres")
            resp.raise_for_status()
            return resp.json()

    def get_trends(self, days: int = 30) -> list:
        with self._client() as client:
            resp = client.get("/admin/stats/trends", params={"days": days})
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Loans
    # ------------------------------------------------------------------

    def checkout_book(self, student_id: str, book_id: str, due_days: int = 14) -> dict:
        with self._client() as client:
            resp = client.post(
                "/loans/checkout",
                json={"student_id": student_id, "book_id": book_id, "due_days": due_days},
            )
            resp.raise_for_status()
            return resp.json()

    def return_loan(self, loan_id: int, notes: str = None) -> dict:
        with self._client() as client:
            payload = {"notes": notes} if notes else {}
            resp = client.post(f"/loans/{loan_id}/return", json=payload)
            resp.raise_for_status()
            return resp.json()

    def renew_loan(self, loan_id: int, additional_days: int = 14) -> dict:
        with self._client() as client:
            resp = client.post(
                f"/loans/{loan_id}/renew",
                json={"additional_days": additional_days},
            )
            resp.raise_for_status()
            return resp.json()

    def get_active_loans(self, limit: int = 100) -> list:
        with self._client() as client:
            resp = client.get("/loans/active", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()

    def get_overdue_loans(self) -> list:
        with self._client() as client:
            resp = client.get("/loans/overdue")
            resp.raise_for_status()
            return resp.json()

    def get_loan_summary(self) -> dict:
        with self._client() as client:
            resp = client.get("/loans/summary")
            resp.raise_for_status()
            return resp.json()

    def get_student_loans(self, student_id: str, active_only: bool = False) -> list:
        with self._client() as client:
            resp = client.get(
                f"/loans/student/{student_id}",
                params={"active_only": active_only},
            )
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Review Moderation
    # ------------------------------------------------------------------

    def get_flagged_reviews(self, limit: int = 50) -> list:
        with self._client() as client:
            resp = client.get("/reviews/flagged", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()

    def trigger_review_scan(self, limit: int = 50) -> dict:
        with self._client() as client:
            resp = client.post("/reviews/scan-pending", params={"limit": limit})
            resp.raise_for_status()
            return resp.json()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self) -> dict:
        with self._client() as client:
            resp = client.get("/health")
            resp.raise_for_status()
            return resp.json()


# Singleton instance
api = APIClient()
