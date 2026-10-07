import os
from datetime import datetime, timezone

from db.mongo import get_db
from exceptions import DocumentError, EduPilotError, IngestionError
from services.embedding_service import embed_texts
from utils.pdf_utils import extract_pdf_pages
from utils.text_utils import chunk_text, clean_text


def build_chunks(document_id, filename, pages):
    """Clean and chunk each page; every chunk remembers its page number."""
    chunks = []
    for page in pages:
        text = clean_text(page["text"])
        for index, chunk in enumerate(chunk_text(text)):
            chunks.append({
                "document_id": document_id,
                "filename": filename,
                "page": page["page"],
                "chunk_index": index,
                "text": chunk,
            })
    return chunks


def ingest_document(file):
    """PDF -> pages -> clean -> chunks -> embeddings -> MongoDB."""
    db = get_db()
    filename = os.path.basename(file.filename)
    document_id = db.documents.insert_one({
        "filename": filename,
        "uploaded_at": datetime.now(timezone.utc),
        "status": "processing",
    }).inserted_id

    try:
        pages = extract_pdf_pages(file)
        chunks = build_chunks(document_id, filename, pages)
        if not chunks:
            raise DocumentError(
                "No extractable text found. Scanned or image-only PDFs are not supported."
            )

        vectors = embed_texts([chunk["text"] for chunk in chunks])
        for chunk, vector in zip(chunks, vectors):
            chunk["embedding"] = vector

        db.chunks.insert_many(chunks)
        db.documents.update_one(
            {"_id": document_id},
            {"$set": {"chunk_count": len(chunks), "status": "ready"}},
        )
    except Exception as exc:
        db.chunks.delete_many({"document_id": document_id})  # no half-ingested documents
        db.documents.update_one(
            {"_id": document_id},
            {"$set": {"status": "failed", "error": str(exc)[:500]}},
        )
        if isinstance(exc, EduPilotError):
            raise
        raise IngestionError(f"Document ingestion failed: {exc}") from exc

    return {
        "document_id": str(document_id),
        "filename": filename,
        "chunk_count": len(chunks),
    }


def list_documents(limit=50):
    """Document metadata for the dashboard, newest first."""
    db = get_db()
    cursor = db.documents.find().sort("uploaded_at", -1).limit(limit)
    return [
        {
            "document_id": str(doc["_id"]),
            "filename": doc.get("filename"),
            "status": doc.get("status"),
            "chunk_count": doc.get("chunk_count", 0),
            "uploaded_at": doc["uploaded_at"].isoformat() if doc.get("uploaded_at") else None,
        }
        for doc in cursor
    ]
