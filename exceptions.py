"""Application errors. Each carries the HTTP status the API should return."""


class EduPilotError(Exception):
    status_code = 500


class DocumentError(EduPilotError):
    """The uploaded PDF cannot be processed (corrupt, encrypted, no text)."""
    status_code = 422


class IngestionError(EduPilotError):
    """Ingestion failed for a reason that is not the user's file."""
    status_code = 500


class DatabaseUnavailable(EduPilotError):
    status_code = 503


class RetrievalError(EduPilotError):
    status_code = 503


class LLMError(EduPilotError):
    status_code = 502
