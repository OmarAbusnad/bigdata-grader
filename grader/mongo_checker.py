from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any

BUSINESS_KEY_ALIASES = ('order_id', 'id_order', 'record_clean.order_id', 'record_clean.id_order')
ROW_ALIASES = ('source_row_number', 'number_row_source', 'row_number', 'csv_row_number')
ENGINE_ALIASES = ('engine_used', 'used_engine', 'engine', 'processing_engine')

@dataclass
class MongoSnapshot:
    raw: int
    validated: int
    quarantine: int
    duplicate_business_keys: int
    business_key: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class MongoChecker:
    def __init__(self, uri: str, database: str, collections: dict[str, str], business_key: str = 'order_id'):
        from pymongo import MongoClient
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        self.database_name = database
        self.db = self.client[database]
        self.collections = collections
        self.business_key = business_key or 'order_id'

    def close(self):
        try:
            self.client.close()
        except Exception:
            pass

    def ping(self) -> bool:
        self.client.admin.command('ping')
        return True

    def drop_database(self):
        self.client.drop_database(self.database_name)
        self.db = self.client[self.database_name]

    def clear_documents(self):
        for name in self.collections.values():
            if name in self.db.list_collection_names():
                self.db[name].delete_many({})

    def reset(self, preserve_schema: bool = True):
        if preserve_schema:
            self.clear_documents()
        else:
            self.drop_database()

    def counts(self) -> dict[str, int]:
        names = set(self.db.list_collection_names())
        return {
            k: (self.db[v].count_documents({}) if v in names else 0)
            for k, v in self.collections.items()
        }

    def _existing_business_key(self) -> str:
        col_name = self.collections['validated']
        if col_name not in self.db.list_collection_names():
            return self.business_key
        col = self.db[col_name]
        for candidate in [self.business_key, *BUSINESS_KEY_ALIASES]:
            try:
                if col.find_one({candidate: {'$exists': True, '$ne': None}}, {candidate: 1}):
                    return candidate
            except Exception:
                continue
        # Indexes are another strong signal even if collection is empty.
        try:
            for idx in col.list_indexes():
                keys = list((idx.get('key') or {}).keys())
                for candidate in [self.business_key, *BUSINESS_KEY_ALIASES]:
                    if candidate in keys:
                        return candidate
        except Exception:
            pass
        return self.business_key

    def duplicate_count(self) -> tuple[int, str]:
        col_name = self.collections['validated']
        if col_name not in self.db.list_collection_names():
            return 0, self.business_key
        key = self._existing_business_key()
        col = self.db[col_name]
        pipeline = [
            {'$match': {key: {'$exists': True, '$ne': None}}},
            {'$group': {'_id': f'${key}', 'n': {'$sum': 1}}},
            {'$match': {'n': {'$gt': 1}}},
            {'$count': 'groups'},
        ]
        docs = list(col.aggregate(pipeline, allowDiskUse=True))
        return (docs[0]['groups'] if docs else 0), key

    def indexes(self, collection_key: str = 'validated') -> list[dict[str, Any]]:
        name = self.collections[collection_key]
        if name not in self.db.list_collection_names():
            return []
        return [dict(x) for x in self.db[name].list_indexes()]

    def has_unique_business_index(self) -> tuple[bool, list[str]]:
        evidence = []
        candidates = {self.business_key, *BUSINESS_KEY_ALIASES}
        for idx in self.indexes('validated'):
            keys = list((idx.get('key') or {}).keys())
            if idx.get('unique') and any(k in candidates for k in keys):
                evidence.append(f"{idx.get('name')}: {keys}")
        return bool(evidence), evidence

    def validator(self, collection_key: str = 'validated') -> dict[str, Any] | None:
        name = self.collections[collection_key]
        try:
            result = self.db.command({'listCollections': 1, 'filter': {'name': name}})
            batch = result.get('cursor', {}).get('firstBatch', [])
            if not batch:
                return None
            options = batch[0].get('options', {})
            return options.get('validator')
        except Exception:
            return None

    def has_json_schema_validator(self) -> bool:
        v = self.validator('validated') or {}
        return '$jsonSchema' in v or any('$jsonSchema' in (x if isinstance(x, dict) else {}) for x in v.get('$and', []))

    def find_validated(self, order_id: str) -> dict[str, Any] | None:
        name = self.collections['validated']
        if name not in self.db.list_collection_names():
            return None
        clauses = []
        for key in [self.business_key, *BUSINESS_KEY_ALIASES]:
            if key not in [next(iter(c), None) for c in clauses]:
                clauses.append({key: order_id})
        return self.db[name].find_one({'$or': clauses})

    def find_raw_by_row(self, data_row_number: int) -> dict[str, Any] | None:
        name = self.collections['raw']
        if name not in self.db.list_collection_names():
            return None
        values = {data_row_number, data_row_number + 1}
        clauses = [{field: {'$in': list(values)}} for field in ROW_ALIASES]
        return self.db[name].find_one({'$or': clauses})

    def sample_docs(self, collection_key: str, n: int = 20) -> list[dict[str, Any]]:
        name = self.collections[collection_key]
        if name not in self.db.list_collection_names():
            return []
        return list(self.db[name].find({}).limit(n))

    def distinct_engine_values(self, n: int = 100) -> list[str]:
        name = self.collections['raw']
        if name not in self.db.list_collection_names():
            return []
        col = self.db[name]
        values: set[str] = set()
        for doc in col.find({}).limit(n):
            for field in ENGINE_ALIASES:
                if doc.get(field) is not None:
                    values.add(str(doc[field]))
        return sorted(values)

    def snapshot(self) -> MongoSnapshot:
        c = self.counts()
        dup, key = self.duplicate_count()
        return MongoSnapshot(c.get('raw', 0), c.get('validated', 0), c.get('quarantine', 0), dup, key)
