from flask import Blueprint, jsonify, request

from config import DEFAULT_HISTORY_LIMIT, MAX_QUESTION_CHARS
from services.document_service import ingest_document, list_documents
from services.rag_service import answer_question, list_queries

api = Blueprint("api", __name__)


def _error(message, status):
    return jsonify({"error": message}), status


@api.post("/documents")
def upload_document():
    file = request.files.get("file")
    if not file or not file.filename:
        return _error("No file uploaded", 400)
    if not file.filename.lower().endswith(".pdf"):
        return _error("Only PDF files are supported", 400)

    return jsonify(ingest_document(file)), 201


@api.post("/query")
def query():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}
    question = data.get("question")
    if not isinstance(question, str) or not question.strip():
        return _error("Question is required", 400)
    question = question.strip()
    if len(question) > MAX_QUESTION_CHARS:
        return _error(f"Question must be at most {MAX_QUESTION_CHARS} characters", 400)

    return jsonify(answer_question(question)), 200


@api.get("/documents")
def documents():
    return jsonify({"documents": list_documents()}), 200


@api.get("/queries")
def queries():
    limit = request.args.get("limit", default=DEFAULT_HISTORY_LIMIT, type=int)
    limit = max(1, min(limit, 100))
    return jsonify({"queries": list_queries(limit)}), 200
