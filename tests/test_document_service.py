import io
import unittest
from unittest.mock import patch

from config import ConfigError
from exceptions import DocumentError, IngestionError
from services import document_service
from tests.fakes import FakeDB


class FakeUpload:
    def __init__(self, filename):
        self.filename = filename


def run_ingest(db, pages=None, embed=None, filename="paper.pdf"):
    embed = embed or (lambda texts: [[0.1, 0.2]] * len(texts))
    with patch.object(document_service, "get_db", return_value=db), \
         patch.object(document_service, "extract_pdf_pages", return_value=pages), \
         patch.object(document_service, "embed_texts", side_effect=embed):
        return document_service.ingest_document(FakeUpload(filename))


class IngestTests(unittest.TestCase):
    def test_successful_ingestion_stores_chunks_with_page_and_embedding(self):
        db = FakeDB()
        words = " ".join(f"w{i}" for i in range(500))   # 450 + overlap -> 2 chunks on page 1
        pages = [{"page": 1, "text": words}, {"page": 3, "text": "short page text"}]
        result = run_ingest(db, pages=pages)

        self.assertEqual(result["chunk_count"], 3)
        self.assertEqual(result["filename"], "paper.pdf")
        doc = db.documents.docs[0]
        self.assertEqual(doc["status"], "ready")
        self.assertEqual(doc["chunk_count"], 3)
        self.assertEqual(result["document_id"], str(doc["_id"]))

        stored = db.chunks.docs
        self.assertEqual([c["page"] for c in stored], [1, 1, 3])
        self.assertEqual([c["chunk_index"] for c in stored], [0, 1, 0])
        self.assertTrue(all(c["document_id"] == doc["_id"] and c["embedding"] for c in stored))

    def test_text_is_cleaned_before_chunking(self):
        db = FakeDB()
        run_ingest(db, pages=[{"page": 1, "text": "line one\n\nline   two"}])
        self.assertEqual(db.chunks.docs[0]["text"], "line one line two")

    def test_filename_path_components_are_stripped(self):
        db = FakeDB()
        result = run_ingest(db, pages=[{"page": 1, "text": "x y"}], filename="../../etc/p.pdf")
        self.assertEqual(result["filename"], "p.pdf")

    def test_pdf_without_text_marks_document_failed(self):
        db = FakeDB()
        with self.assertRaises(DocumentError):
            run_ingest(db, pages=[])
        self.assertEqual(db.documents.docs[0]["status"], "failed")
        self.assertEqual(db.chunks.docs, [])

    def test_embedding_failure_marks_failed_and_wraps_error(self):
        db = FakeDB()
        def broken(_):
            raise RuntimeError("model unavailable")
        with self.assertRaises(IngestionError):
            run_ingest(db, pages=[{"page": 1, "text": "some text"}], embed=broken)
        self.assertEqual(db.documents.docs[0]["status"], "failed")
        self.assertIn("model unavailable", db.documents.docs[0]["error"])

    def test_database_write_failure_cleans_up_chunks(self):
        db = FakeDB(fail_insert_many=True)
        with self.assertRaises(IngestionError):
            run_ingest(db, pages=[{"page": 1, "text": "some text"}])
        self.assertEqual(db.chunks.docs, [])
        self.assertEqual(db.documents.docs[0]["status"], "failed")

    def test_missing_mongodb_uri_raises_config_error(self):
        import os
        from db import mongo
        mongo._client = None
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ConfigError) as ctx:
                mongo.get_db()
        self.assertIn("MONGODB_URI", str(ctx.exception))


try:
    import fitz  # noqa: F401
    from reportlab.pdfgen import canvas
    HAVE_PDF_LIBS = True
except ImportError:
    HAVE_PDF_LIBS = False


@unittest.skipUnless(HAVE_PDF_LIBS, "needs PyMuPDF and reportlab (pip install -r requirements-dev.txt)")
class RealPdfExtractionTests(unittest.TestCase):
    def _make_pdf(self, page_texts):
        buf = io.BytesIO()
        c = canvas.Canvas(buf)
        for text in page_texts:
            if text:
                c.drawString(72, 720, text)
            c.showPage()
        c.save()
        buf.seek(0)
        return buf

    def test_extracts_text_with_one_indexed_pages_and_skips_blank_pages(self):
        from utils.pdf_utils import extract_pdf_pages
        pages = extract_pdf_pages(self._make_pdf(["First page", "", "Third page"]))
        self.assertEqual([p["page"] for p in pages], [1, 3])
        self.assertIn("First page", pages[0]["text"])

    def test_corrupt_pdf_raises_document_error(self):
        from utils.pdf_utils import extract_pdf_pages
        with self.assertRaises(DocumentError):
            extract_pdf_pages(io.BytesIO(b"this is not a pdf"))


if __name__ == "__main__":
    unittest.main()
