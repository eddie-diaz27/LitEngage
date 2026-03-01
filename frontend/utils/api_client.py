"""HTTP client for communicating with the FastAPI backend."""

import os

import httpx


BACKEND_URL = os.environ.get("BACKEND_API_URL", "http://localhost:8000")


class APIClient:
    """Synchronous API client for Streamlit (runs in sync context)."""

    def __init__(self, base_url: str = BACKEND_URL):
        self.base_url = f"{base_url}/api"

    def _client(self) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=60.0)

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

    def get_reading_history(self, student_id: str) -> list:
        with self._client() as client:
            resp = client.get(f"/students/{student_id}/history")
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

    def search_books(self, query: str, reading_level: str = None, max_results: int = 10) -> list:
        payload = {"query": query, "max_results": max_results}
        if reading_level:
            payload["reading_level"] = reading_level

        with self._client() as client:
            resp = client.post("/books/search", json=payload)
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
