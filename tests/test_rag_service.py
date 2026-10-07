import unittest
from unittest.mock import patch

from exceptions import LLMError, RetrievalError
from services import rag_service
from tests.fakes import FakeDB


CHUNKS = [
    {
        "_id": "c1",
        "filename": "a.pdf",
        "page": 2,
        "text": "Alpha text.",
        "score": 0.91,
    },
    {
        "_id": "c2",
        "filename": "b.pdf",
        "page": 7,
        "text": "Beta text.",
        "score": 0.84,
    },
]


class FakeLLM:
    """Fake Ollama client used for testing."""

    def __init__(self, reply="The answer.", fail=False):
        self.calls = []
        self.reply = reply
        self.fail = fail

    def chat(self, model, messages):
        if self.fail:
            raise RuntimeError("429 rate limited")

        self.calls.append(
            {
                "model": model,
                "messages": messages,
            }
        )

        return {
            "message": {
                "content": self.reply
            }
        }


class RetrievalTests(unittest.TestCase):

    def test_question_is_embedded_and_vector_search_pipeline_built(self):
        db = FakeDB(aggregate_result=CHUNKS)

        with (
            patch.object(rag_service, "get_db", return_value=db),
            patch.object(
                rag_service,
                "embed_texts",
                return_value=[[0.5, 0.5]],
            ) as embed,
        ):
            results = rag_service.retrieve_chunks("what is alpha?")

        embed.assert_called_once_with(["what is alpha?"])

        stage = db.chunks.last_pipeline[0]["$vectorSearch"]

        self.assertEqual(
            stage["index"],
            "chunk_vector_index",
        )

        self.assertEqual(
            stage["path"],
            "embedding",
        )

        self.assertEqual(
            stage["queryVector"],
            [0.5, 0.5],
        )

        self.assertEqual(
            (stage["numCandidates"], stage["limit"]),
            (50, 5),
        )

        self.assertEqual(
            db.chunks.last_pipeline[1]["$project"]["score"],
            {"$meta": "vectorSearchScore"},
        )

        self.assertEqual(
            results,
            CHUNKS,
        )

    def test_vector_search_failure_becomes_retrieval_error(self):
        db = FakeDB()

        db.chunks.aggregate = (
            lambda p: (_ for _ in ()).throw(
                RuntimeError("index not found")
            )
        )

        with (
            patch.object(rag_service, "get_db", return_value=db),
            patch.object(
                rag_service,
                "embed_texts",
                return_value=[[0.1]],
            ),
        ):
            with self.assertRaises(RetrievalError) as ctx:
                rag_service.retrieve_chunks("q")

        self.assertIn(
            "chunk_vector_index",
            str(ctx.exception),
        )


class ContextTests(unittest.TestCase):

    def test_context_labels_each_chunk_with_source_file_and_page(self):
        ctx = rag_service.build_context(CHUNKS)

        self.assertIn(
            "[Source 1 | a.pdf | page 2]\nAlpha text.",
            ctx,
        )

        self.assertIn(
            "[Source 2 | b.pdf | page 7]\nBeta text.",
            ctx,
        )

        self.assertLess(
            ctx.index("Source 1"),
            ctx.index("Source 2"),
        )


class GenerationTests(unittest.TestCase):

    def test_prompt_is_grounded_and_contains_context_and_question(self):
        llm = FakeLLM()

        with patch.object(
            rag_service,
            "get_llm_client",
            return_value=llm,
        ):
            answer = rag_service.generate_answer(
                "What is alpha?",
                "CTX-BLOCK",
            )

        self.assertEqual(
            answer,
            "The answer.",
        )

        call = llm.calls[0]

        self.assertEqual(
            call["model"],
            "mistral:latest",
        )

        system, user = call["messages"]

        self.assertEqual(
            system["role"],
            "system",
        )

        self.assertIn(
            "Answer only using the supplied research context",
            system["content"],
        )

        self.assertIn(
            "Do not invent facts",
            system["content"],
        )

        self.assertIn(
            "CTX-BLOCK",
            user["content"],
        )

        self.assertIn(
            "What is alpha?",
            user["content"],
        )

    def test_llm_api_failure_becomes_llm_error(self):
        with patch.object(
            rag_service,
            "get_llm_client",
            return_value=FakeLLM(fail=True),
        ):
            with self.assertRaises(LLMError):
                rag_service.generate_answer(
                    "q",
                    "c",
                )

    def test_local_ollama_client_is_used(self):
        fake_client = object()

        with patch(
            "ollama.Client",
            return_value=fake_client,
        ) as client:

            rag_service._llm_client = None

            result = rag_service.get_llm_client()

        self.assertIs(
            result,
            fake_client,
        )

        client.assert_called_once_with(
            host="http://localhost:11434"
        )

        rag_service._llm_client = None


class AnswerQuestionTests(unittest.TestCase):

    def test_full_flow_retrieves_then_generates_logs_and_returns_sources(self):
        db = FakeDB()

        with (
            patch.object(
                rag_service,
                "get_db",
                return_value=db,
            ),
            patch.object(
                rag_service,
                "retrieve_chunks",
                return_value=CHUNKS,
            ),
            patch.object(
                rag_service,
                "generate_answer",
                return_value="Grounded.",
            ) as gen,
        ):
            result = rag_service.answer_question("q?")

        question, context = gen.call_args.args

        self.assertEqual(
            question,
            "q?",
        )

        self.assertIn(
            "Alpha text.",
            context,
        )

        self.assertEqual(
            result["answer"],
            "Grounded.",
        )

        self.assertEqual(
            result["sources"][0],
            {
                "filename": "a.pdf",
                "page": 2,
                "score": 0.91,
            },
        )

        logged = db.queries.docs[0]

        self.assertEqual(
            logged["question"],
            "q?",
        )

        self.assertEqual(
            logged["retrieved_chunks"][0],
            {
                "chunk_id": "c1",
                "score": 0.91,
            },
        )

        self.assertIn(
            "created_at",
            logged,
        )

    def test_no_retrieval_skips_llm_and_returns_fixed_answer(self):
        db = FakeDB()

        with (
            patch.object(
                rag_service,
                "get_db",
                return_value=db,
            ),
            patch.object(
                rag_service,
                "retrieve_chunks",
                return_value=[],
            ),
            patch.object(
                rag_service,
                "generate_answer",
            ) as gen,
        ):
            result = rag_service.answer_question("anything")

        gen.assert_not_called()

        self.assertEqual(
            result,
            {
                "answer": "I could not find relevant information.",
                "sources": [],
            },
        )

        self.assertEqual(
            db.queries.docs[0]["retrieved_chunks"],
            [],
        )

    def test_llm_failure_is_not_logged_as_a_successful_query(self):
        db = FakeDB()

        with (
            patch.object(
                rag_service,
                "get_db",
                return_value=db,
            ),
            patch.object(
                rag_service,
                "retrieve_chunks",
                return_value=CHUNKS,
            ),
            patch.object(
                rag_service,
                "generate_answer",
                side_effect=LLMError("down"),
            ),
        ):
            with self.assertRaises(LLMError):
                rag_service.answer_question("q")

        self.assertEqual(
            db.queries.docs,
            [],
        )


if __name__ == "__main__":
    unittest.main()