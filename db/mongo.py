"""MongoDB connection. The client is created lazily and cached."""
from config import get_db_name, require_env
from exceptions import DatabaseUnavailable

_client = None


def get_db():
    """Return the application database, connecting on first use.

    Raises ConfigError if MONGODB_URI is missing and DatabaseUnavailable if
    the server cannot be reached.
    """
    global _client
    if _client is None:
        uri = require_env("MONGODB_URI")
        from pymongo import MongoClient

        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        try:
            client.admin.command("ping")
        except Exception as exc:
            client.close()
            raise DatabaseUnavailable(
                "Could not connect to MongoDB. Check MONGODB_URI and Atlas network access."
            ) from exc
        _client = client
    return _client[get_db_name()]
