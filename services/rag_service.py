from datetime import datetime, timezone

from config import (
    DEFAULT_HISTORY_LIMIT,
    NUM_CANDIDATES,
    TOP_K,
    VECTOR_FIELD,
    VECTOR_INDEX_NAME,
    get_ollama_host,
    get_ollama_model,
)
from db.mongo import get_db
from exceptions import LLMError, RetrievalError
from services.embedding_service import embed_texts


NO_ANSWER = "I could not find relevant information."


SYSTEM_PROMPT = """You are an academic research assistant.
Answer only using the supplied research context.
If the context does not contain enough information,
say that the information is not available.
Do not invent facts."""


_llm_client = None


def retrieve_chunks(question, limit=TOP_K):
    """Embed the question and run an Atlas $vectorSearch over stored chunks."""
    query_vector = embed_texts([question])[0]

    pipeline = [
        {
            "$vectorSearch": {
                "index": VECTOR_INDEX_NAME,
                "path": VECTOR_FIELD,
                "queryVector": query_vector,
                "numCandidates": NUM_CANDIDATES,
                "limit": limit,
            }
        },
        {
            "$project": {
                "_id": 1,
                "document_id": 1,
                "filename": 1,
                "page": 1,
                "chunk_index": 1,
                "text": 1,
                "score": {"$meta": "vectorSearchScore"},
            }
        },
    ]

    try:
        return list(get_db().chunks.aggregate(pipeline))
    except Exception as exc:
        raise RetrievalError(
            f"Vector search failed. Make sure the Atlas index "
            f"'{VECTOR_INDEX_NAME}' exists and is queryable (see README)."
        ) from exc


def build_context(results):
    """Join retrieved chunks, each labelled with its filename and page."""
    return "\n\n".join(
        f"[Source {i} | {r['filename']} | page {r['page']}]\n{r['text']}"
        for i, r in enumerate(results, start=1)
    )


def get_llm_client():
    """Return a client connected to the local Ollama server."""
    global _llm_client

    if _llm_client is None:
        try:
            import ollama
        except ImportError as exc:
            raise LLMError(
                "The ollama Python package is not installed. "
                "Run: pip install ollama"
            ) from exc

        try:
            _llm_client = ollama.Client(host=get_ollama_host())
        except Exception as exc:
            raise LLMError(
                f"Could not connect to the local Ollama server: {exc}"
            ) from exc

    return _llm_client


def generate_answer(question, context):
    """Ask the local Mistral model through Ollama."""
    client = get_llm_client()

    user_prompt = (
        f"Research context:\n{context}\n\n"
        f"Question:\n{question}"
    )

    try:
        response = client.chat(
            model=get_ollama_model(),
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_prompt,
                },
            ],
        )

        return response["message"]["content"]

    except Exception as exc:
        raise LLMError(
            f"The local language model request failed: {exc}"
        ) from exc


def answer_question(question):
    """question -> embedding -> retrieval -> context -> LLM -> answer + sources."""
    db = get_db()
    results = retrieve_chunks(question)

    if not results:
        db.queries.insert_one(
            {
                "question": question,
                "answer": NO_ANSWER,
                "retrieved_chunks": [],
                "created_at": datetime.now(timezone.utc),
            }
        )

        return {
            "answer": NO_ANSWER,
            "sources": [],
        }

    answer = generate_answer(
        question,
        build_context(results),
    )

    db.queries.insert_one(
        {
            "question": question,
            "answer": answer,
            "retrieved_chunks": [
                {
                    "chunk_id": r["_id"],
                    "score": r["score"],
                }
                for r in results
            ],
            "created_at": datetime.now(timezone.utc),
        }
    )

    return {
        "answer": answer,
        "sources": [
            {
                "filename": r["filename"],
                "page": r["page"],
                "score": r["score"],
            }
            for r in results
        ],
    }


def list_queries(limit=DEFAULT_HISTORY_LIMIT):
    """Query history, newest first."""
    cursor = (
        get_db()
        .queries
        .find()
        .sort("created_at", -1)
        .limit(limit)
    )

    return [
        {
            "question": q.get("question"),
            "answer": q.get("answer"),
            "created_at": (
                q["created_at"].isoformat()
                if q.get("created_at")
                else None
            ),
        }
        for q in cursor
    ]