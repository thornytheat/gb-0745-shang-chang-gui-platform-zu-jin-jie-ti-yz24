import json
import sqlite3
from contextlib import closing
from pathlib import Path


class RunStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.execute("CREATE TABLE IF NOT EXISTS runs (id TEXT PRIMARY KEY, payload TEXT NOT NULL)")

    def connect(self):
        return sqlite3.connect(self.path, timeout=10)

    def get(self, run_id):
        with closing(self.connect()) as db:
            row = db.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def save(self, run_id, data):
        with closing(self.connect()) as db, db:
            result = db.execute(
                "INSERT OR IGNORE INTO runs VALUES (?, ?)", (run_id, json.dumps(data, ensure_ascii=False))
            )
            created = result.rowcount == 1
            payload = db.execute("SELECT payload FROM runs WHERE id=?", (run_id,)).fetchone()[0]
        return json.loads(payload), not created

    def history(self):
        with closing(self.connect()) as db:
            return [
                json.loads(row[0])["运行清单"]
                for row in db.execute("SELECT payload FROM runs ORDER BY rowid DESC LIMIT 40")
            ]
