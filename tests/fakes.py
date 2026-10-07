"""Tiny in-memory stand-in for the MongoDB database, used only at the DB boundary."""
from itertools import count


class _InsertResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class FakeCollection:
    def __init__(self, aggregate_result=None, fail_insert_many=False):
        self.docs = []
        self._ids = count(1)
        self.aggregate_result = aggregate_result or []
        self.last_pipeline = None
        self.fail_insert_many = fail_insert_many

    def insert_one(self, doc):
        doc = dict(doc)
        doc.setdefault("_id", next(self._ids))
        self.docs.append(doc)
        return _InsertResult(doc["_id"])

    def insert_many(self, docs):
        if self.fail_insert_many:
            raise RuntimeError("write failed")
        for doc in docs:
            self.insert_one(doc)

    def update_one(self, query, update):
        for doc in self.docs:
            if all(doc.get(k) == v for k, v in query.items()):
                doc.update(update["$set"])
                return

    def delete_many(self, query):
        self.docs = [d for d in self.docs
                     if not all(d.get(k) == v for k, v in query.items())]

    def aggregate(self, pipeline):
        self.last_pipeline = pipeline
        return iter(self.aggregate_result)


class FakeDB:
    def __init__(self, **kwargs):
        self.documents = FakeCollection()
        self.chunks = FakeCollection(
            aggregate_result=kwargs.get("aggregate_result"),
            fail_insert_many=kwargs.get("fail_insert_many", False),
        )
        self.queries = FakeCollection()
