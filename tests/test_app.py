import tempfile
import unittest
from pathlib import Path

from app import create_app


class BlogApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "test.sqlite3")
        self.app = create_app({"TESTING": True, "SECRET_KEY": "test-secret", "DATABASE": self.db_path})
        self.client = self.app.test_client()
        self.refresh_csrf()

    def tearDown(self):
        self.temp_dir.cleanup()

    def refresh_csrf(self):
        response = self.client.get("/api/auth/csrf")
        self.csrf = response.get_json()["csrfToken"]

    def write(self, path, data=None, method="post"):
        response = getattr(self.client, method)(
            path,
            json=data or {},
            headers={"X-CSRF-Token": self.csrf},
        )
        return response

    def register(self, username="Rowan", email="rowan@example.com"):
        response = self.write("/api/auth/register", {"username": username, "email": email, "password": "thoughtful123"})
        self.refresh_csrf()
        return response

    def create_post(self, title="A small beginning"):
        return self.write("/api/posts", {"title": title, "body": "A thoughtful story that has more than twenty characters.", "category": "Life"})

    def test_register_and_create_post(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        post = self.create_post()
        self.assertEqual(post.status_code, 201)
        listing = self.client.get("/api/posts").get_json()["posts"]
        self.assertEqual(listing[0]["title"], "A small beginning")
        self.assertEqual(listing[0]["author"], "Rowan")

    def test_post_edit_delete_require_ownership(self):
        self.register()
        post_id = self.create_post().get_json()["id"]
        self.write("/api/auth/logout")
        self.refresh_csrf()
        self.register("Sage", "sage@example.com")
        forbidden = self.write(f"/api/posts/{post_id}", {"title": "Edited", "body": "A thoughtful story that has more than twenty characters."}, "put")
        self.assertEqual(forbidden.status_code, 403)
        denied_delete = self.write(f"/api/posts/{post_id}", method="delete")
        self.assertEqual(denied_delete.status_code, 403)

    def test_owner_can_edit_and_delete_post(self):
        self.register()
        post_id = self.create_post().get_json()["id"]
        updated = self.write(
            f"/api/posts/{post_id}",
            {"title": "A new beginning", "body": "A thoughtful story that has more than twenty characters.", "category": "Notes"},
            "put",
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(self.client.get(f"/api/posts/{post_id}").get_json()["post"]["title"], "A new beginning")
        deleted = self.write(f"/api/posts/{post_id}", method="delete")
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(self.client.get(f"/api/posts/{post_id}").status_code, 404)

    def test_comments_require_authentication(self):
        self.register()
        post_id = self.create_post().get_json()["id"]
        self.write("/api/auth/logout")
        self.refresh_csrf()
        response = self.write(f"/api/posts/{post_id}/comments", {"body": "A lovely thought."})
        self.assertEqual(response.status_code, 401)

    def test_mutations_require_csrf_token(self):
        response = self.client.post("/api/auth/register", json={"username": "Rowan", "email": "rowan@example.com", "password": "thoughtful123"})
        self.assertEqual(response.status_code, 403)

    def test_search_and_comment_round_trip(self):
        self.register()
        post_id = self.create_post("A note about gardens").get_json()["id"]
        result = self.write(f"/api/posts/{post_id}/comments", {"body": "The garden is a lovely place to begin."})
        self.assertEqual(result.status_code, 201)
        detail = self.client.get(f"/api/posts/{post_id}").get_json()
        self.assertEqual(detail["comments"][0]["body"], "The garden is a lovely place to begin.")
        search = self.client.get("/api/posts?q=gardens").get_json()["posts"]
        self.assertEqual(len(search), 1)


if __name__ == "__main__":
    unittest.main()
