from config import EMBEDDING_MODEL

_model = None


def get_model():
    """Load the Sentence Transformer once (first use), then reuse it."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(EMBEDDING_MODEL)
    return _model


def embed_texts(texts):
    """Embed chunks and questions with the same model so vectors are comparable.

    Vectors are L2-normalised and returned as plain lists (BSON-storable).
    """
    if not texts:
        return []
    vectors = get_model().encode(
        texts, normalize_embeddings=True, convert_to_numpy=True
    )
    return vectors.tolist()
