"""Central configuration. Secrets come from environment variables only."""
import os

# --- RAG parameters (from the project specification) ---
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384          # output size of bge-small-en-v1.5
CHUNK_SIZE = 450                    # words per chunk
CHUNK_OVERLAP = 75                  # words shared between consecutive chunks
TOP_K = 5                           # chunks passed to the LLM
NUM_CANDIDATES = 50                 # ANN candidates examined by $vectorSearch
VECTOR_INDEX_NAME = "chunk_vector_index"
VECTOR_FIELD = "embedding"

# --- API limits ---
MAX_QUESTION_CHARS = 2000
DEFAULT_HISTORY_LIMIT = 20


class ConfigError(Exception):
    """A required environment variable is missing."""


def require_env(name):
    value = os.environ.get(name, "").strip()
    if not value:
        raise ConfigError(
            f"Environment variable {name} is not set. Copy .env.example to .env and fill it in."
        )
    return value


def get_db_name():
    return os.environ.get("MONGODB_DB", "edupilot")


def get_ollama_host():
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434")


def get_ollama_model():
    return os.environ.get("OLLAMA_MODEL", "mistral:latest")


def get_max_upload_bytes():
    return int(os.environ.get("MAX_UPLOAD_MB", "25")) * 1024 * 1024
