import aiosqlite
import json
from typing import Any

class SQLiteCollection:
    def __init__(self, db_path: str, table_name: str):
        self.db_path = db_path
        self.table_name = table_name

    async def _init_table(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(f"CREATE TABLE IF NOT EXISTS {self.table_name} (id TEXT PRIMARY KEY, data TEXT)")
            await db.commit()

    async def insert_one(self, document: dict[str, Any]):
        doc_id = (
            document.get("id")
            or document.get("report_id")
            or document.get("session_id")
            or str(hash(json.dumps(document, sort_keys=True)))
        )
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"INSERT INTO {self.table_name} (id, data) VALUES (?, ?)",
                (doc_id, json.dumps(document))
            )
            await db.commit()
        return MagicResult(doc_id)

    async def find_one(self, query_filter: dict[str, Any], projection: dict[str, Any] | None = None):
        # Simplified Mongo-to-SQL filter: resolve known document ID fields
        doc_id = (
            query_filter.get("id")
            or query_filter.get("report_id")
            or query_filter.get("session_id")
        )
        sql = f"SELECT data FROM {self.table_name}"
        params = []
        if doc_id:
            sql += " WHERE id = ?"
            params.append(doc_id)

        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql, params) as cursor:
                row = await cursor.fetchone()
                if row:
                    doc = json.loads(row[0])
                    # Handle projection briefly
                    if projection and projection.get("_id") == 0:
                        doc.pop("_id", None)
                    return doc
        return None

    async def update_one(self, query_filter: dict[str, Any], update: dict[str, Any], upsert: bool = False):
        doc_id = (
            query_filter.get("id")
            or query_filter.get("report_id")
            or query_filter.get("session_id")
        )
        if not doc_id:
            return

        existing = await self.find_one(query_filter)
        if not existing:
            if upsert:
                # Handle $set if present
                doc = update.get("$set", update)
                if doc_id:
                    doc["id"] = doc_id
                await self.insert_one(doc)
            return

        # Simple $set merge
        if "$set" in update:
            existing.update(update["$set"])
        else:
            existing.update(update)

        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"UPDATE {self.table_name} SET data = ? WHERE id = ?",
                (json.dumps(existing), doc_id)
            )
            await db.commit()

    def find(self, query_filter: dict[str, Any] | None = None, projection: dict[str, Any] | None = None):
        return SQLiteCursor(self.db_path, self.table_name, query_filter or {}, projection or {})


class SQLiteCursor:
    def __init__(self, db_path: str, table_name: str, query_filter: dict[str, Any], projection: dict[str, Any]):
        self.db_path = db_path
        self.table_name = table_name
        self.query_filter = query_filter or {}
        self.projection = projection or {}
        self._sort = None
        self._limit = None

    def sort(self, key: str, direction: int = -1):
        self._sort = (key, direction)
        return self

    async def to_list(self, length: int = 100):
        sql = f"SELECT data FROM {self.table_name}"
        # We don't implement complex SQL filtering here, we filter in Python for ease of migration
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(sql) as cursor:
                rows = await cursor.fetchall()
                results = [json.loads(r[0]) for r in rows]

        # Simple sorting in Python
        if self._sort:
            key, direction = self._sort
            results.sort(key=lambda x: x.get(key, ""), reverse=(direction == -1))

        return results[:length]

class MagicResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id

class SQLiteDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._collections = {}

    def __getattr__(self, name):
        if name not in self._collections:
            self._collections[name] = SQLiteCollection(self.db_path, name)
        return self._collections[name]

    async def init_all(self):
        # List of tables to initialize
        tables = [
            "app_settings", "governance_audit_logs", "governance_policies",
            "integration_events", "quality_metrics", "reports",
            "repository_sessions", "security_events"
        ]
        for t in tables:
            await self.__getattr__(t)._init_table()
