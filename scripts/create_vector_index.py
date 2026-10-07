"""Create the Atlas Vector Search index used by retrieve_chunks().

Usage (from the project root, with .env filled in):
    python scripts/create_vector_index.py

Requires an Atlas cluster (M0 free tier is enough). The index becomes
queryable after Atlas finishes building it (usually under a minute).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv

load_dotenv()

from pymongo.operations import SearchIndexModel  # noqa: E402

from config import EMBEDDING_DIMENSIONS, VECTOR_FIELD, VECTOR_INDEX_NAME  # noqa: E402
from db.mongo import get_db  # noqa: E402


def main():
    db = get_db()
    if "chunks" not in db.list_collection_names():
        db.create_collection("chunks")
    existing = [idx["name"] for idx in db.chunks.list_search_indexes()]
    if VECTOR_INDEX_NAME in existing:
        print(f"Index '{VECTOR_INDEX_NAME}' already exists.")
        return
    model = SearchIndexModel(
        name=VECTOR_INDEX_NAME,
        type="vectorSearch",
        definition={
            "fields": [{
                "type": "vector",
                "path": VECTOR_FIELD,
                "numDimensions": EMBEDDING_DIMENSIONS,
                "similarity": "cosine",
            }]
        },
    )
    db.chunks.create_search_index(model=model)
    print(f"Created index '{VECTOR_INDEX_NAME}'. Wait until it shows as Active in Atlas.")


if __name__ == "__main__":
    main()
