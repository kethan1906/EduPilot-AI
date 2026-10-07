import io
import unittest
from unittest.mock import patch

from app import create_app
from config import ConfigError
from exceptions import DocumentError, LLMError


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.client = create_app().test_client()

    # --- POST /api/documents validation ---
    def test_upload_without_file_is_400(self):
        r = self.client.post("/api/documents")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "No file uploaded")

    def test_upload_with_empty_filename_is_400(self):
        r = self.client.post("/api/documents", data={"file": (io.BytesIO(b"x"), "")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)

    def test_upload_non_pdf_is_400(self):
        r = self.client.post("/api/documents", data={"file": (io.BytesIO(b"hi"), "notes.txt")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.get_json()["error"], "Only PDF files are supported")

    @patch("routes.api.ingest_document")
    def test_invalid_upload_never_reaches_ingestion(self, ingest):
        self.client.post("/api/documents", data={"file": (io.BytesIO(b"hi"), "a.docx")},
                         content_type="multipart/form-data")
        ingest.assert_not_called()

    @patch("routes.api.ingest_document", return_value={"document_id": "1", "filename": "p.pdf", "chunk_count": 3})
    def test_upload_pdf_success_is_201_case_insensitive_extension(self, ingest):
        r = self.client.post("/api/documents", data={"file": (io.BytesIO(b"%PDF"), "Paper.PDF")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.get_json()["chunk_count"], 3)
        ingest.assert_called_once()

    @patch("routes.api.ingest_document", side_effect=DocumentError("corrupt"))
    def test_unprocessable_pdf_is_422_json(self, _):
        r = self.client.post("/api/documents", data={"file": (io.BytesIO(b"bad"), "x.pdf")},
                             content_type="multipart/form-data")
        self.assertEqual(r.status_code, 422)
        self.assertEqual(r.get_json(), {"error": "corrupt"})

    # --- POST /api/query validation ---
    def test_query_empty_or_missing_question_is_400(self):
        for payload in ({}, {"question": ""}, {"question": "   "}, {"question": 42}, [1, 2]):
            with self.subTest(payload=payload):
                r = self.client.post("/api/query", json=payload)
                self.assertEqual(r.status_code, 400)
                self.assertEqual(r.get_json()["error"], "Question is required")

    def test_query_invalid_json_body_is_400(self):
        r = self.client.post("/api/query", data="not json", content_type="application/json")
        self.assertEqual(r.status_code, 400)

    def test_query_too_long_is_400(self):
        r = self.client.post("/api/query", json={"question": "a" * 2001})
        self.assertEqual(r.status_code, 400)

    @patch("routes.api.answer_question", return_value={"answer": "A", "sources": []})
    def test_query_success_strips_question(self, answer):
        r = self.client.post("/api/query", json={"question": "  what is X?  "})
        self.assertEqual(r.status_code, 200)
        answer.assert_called_once_with("what is X?")

    # --- error mapping ---
    @patch("routes.api.answer_question", side_effect=ConfigError("MISTRAL_API_KEY is not set"))
    def test_missing_config_is_503(self, _):
        r = self.client.post("/api/query", json={"question": "q"})
        self.assertEqual(r.status_code, 503)
        self.assertIn("MISTRAL_API_KEY", r.get_json()["error"])

    @patch("routes.api.answer_question", side_effect=LLMError("upstream down"))
    def test_llm_failure_is_502(self, _):
        r = self.client.post("/api/query", json={"question": "q"})
        self.assertEqual(r.status_code, 502)

    @patch("routes.api.answer_question", side_effect=RuntimeError("boom"))
    def test_unexpected_error_is_500_without_leaking_details(self, _):
        r = self.client.post("/api/query", json={"question": "q"})
        self.assertEqual(r.status_code, 500)
        self.assertEqual(r.get_json(), {"error": "Internal server error"})

    # --- pages ---
    def test_home_page_renders(self):
        r = self.client.get("/")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"EduPilot AI", r.data)


if __name__ == "__main__":
    unittest.main()
