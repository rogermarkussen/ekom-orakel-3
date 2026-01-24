"""
SQLite Knowledge Base for verifiserte spørringer og korreksjoner.

Erstatter QUERY_LOG.md med strukturert database med FTS5 full-text search.

Eksempel:
    from library.knowledge import KnowledgeBase

    kb = KnowledgeBase()

    # Søk etter spørringer
    results = kb.search_queries("fiber spredtbygd")

    # Legg til ny spørring
    kb.add_query(
        question="Fiberdekning i spredtbygd per fylke",
        sql="SELECT ...",
        result_summary="91% nasjonalt",
        category="Dekning",
        tags=["fiber", "spredtbygd", "fylke"]
    )
"""

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Database path
DB_PATH = Path(__file__).parent.parent / "lib" / "knowledge.db"
BACKUP_DIR = Path(__file__).parent.parent / "lib" / "knowledge"


@dataclass
class Query:
    """Verifisert spørring."""
    id: int
    question: str
    sql: str
    result_summary: str
    category: str
    tags: list[str]
    verified_date: str
    promoted: bool = False
    notes: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "question": self.question,
            "sql": self.sql,
            "result_summary": self.result_summary,
            "category": self.category,
            "tags": self.tags,
            "verified_date": self.verified_date,
            "promoted": self.promoted,
            "notes": self.notes,
        }


@dataclass
class Correction:
    """Dokumentert feil og løsning."""
    id: int
    context: str
    error: str
    solution: str
    created_date: str
    pattern: Optional[str] = None  # Regex for automatisk deteksjon

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "context": self.context,
            "error": self.error,
            "solution": self.solution,
            "created_date": self.created_date,
            "pattern": self.pattern,
        }


class KnowledgeBase:
    """SQLite-basert kunnskapsbase med FTS5 søk."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self._ensure_db()

    def _ensure_db(self):
        """Opprett database og tabeller hvis de ikke finnes."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                -- Hovedtabell for spørringer
                CREATE TABLE IF NOT EXISTS queries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    sql TEXT NOT NULL,
                    result_summary TEXT,
                    category TEXT NOT NULL,
                    verified_date TEXT NOT NULL,
                    promoted INTEGER DEFAULT 0,
                    notes TEXT,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                -- Tags for kategorisering
                CREATE TABLE IF NOT EXISTS tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL
                );

                -- Many-to-many mellom queries og tags
                CREATE TABLE IF NOT EXISTS query_tags (
                    query_id INTEGER REFERENCES queries(id) ON DELETE CASCADE,
                    tag_id INTEGER REFERENCES tags(id) ON DELETE CASCADE,
                    PRIMARY KEY (query_id, tag_id)
                );

                -- Korreksjoner / lærte feil
                CREATE TABLE IF NOT EXISTS corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    context TEXT NOT NULL,
                    error TEXT NOT NULL,
                    solution TEXT NOT NULL,
                    pattern TEXT,
                    created_date TEXT NOT NULL,
                    created_at TEXT DEFAULT (datetime('now'))
                );

                -- FTS5 indeks for full-text search på spørringer
                CREATE VIRTUAL TABLE IF NOT EXISTS queries_fts USING fts5(
                    question,
                    sql,
                    result_summary,
                    category,
                    notes,
                    content='queries',
                    content_rowid='id'
                );

                -- Triggers for å holde FTS synkronisert
                CREATE TRIGGER IF NOT EXISTS queries_ai AFTER INSERT ON queries BEGIN
                    INSERT INTO queries_fts(rowid, question, sql, result_summary, category, notes)
                    VALUES (new.id, new.question, new.sql, new.result_summary, new.category, new.notes);
                END;

                CREATE TRIGGER IF NOT EXISTS queries_ad AFTER DELETE ON queries BEGIN
                    INSERT INTO queries_fts(queries_fts, rowid, question, sql, result_summary, category, notes)
                    VALUES ('delete', old.id, old.question, old.sql, old.result_summary, old.category, old.notes);
                END;

                CREATE TRIGGER IF NOT EXISTS queries_au AFTER UPDATE ON queries BEGIN
                    INSERT INTO queries_fts(queries_fts, rowid, question, sql, result_summary, category, notes)
                    VALUES ('delete', old.id, old.question, old.sql, old.result_summary, old.category, old.notes);
                    INSERT INTO queries_fts(rowid, question, sql, result_summary, category, notes)
                    VALUES (new.id, new.question, new.sql, new.result_summary, new.category, new.notes);
                END;

                -- Indekser
                CREATE INDEX IF NOT EXISTS idx_queries_category ON queries(category);
                CREATE INDEX IF NOT EXISTS idx_queries_verified ON queries(verified_date);
                CREATE INDEX IF NOT EXISTS idx_corrections_pattern ON corrections(pattern);
            """)

    # ========== Query CRUD ==========

    def add_query(
        self,
        question: str,
        sql: str,
        result_summary: str,
        category: str,
        tags: list[str],
        verified_date: Optional[str] = None,
        promoted: bool = False,
        notes: Optional[str] = None,
    ) -> int:
        """Legg til ny verifisert spørring."""
        if verified_date is None:
            verified_date = datetime.now().strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO queries (question, sql, result_summary, category, verified_date, promoted, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (question, sql, result_summary, category, verified_date, int(promoted), notes))

            query_id = cursor.lastrowid

            # Legg til tags
            for tag in tags:
                # Opprett tag hvis den ikke finnes
                conn.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag,))
                conn.execute("""
                    INSERT INTO query_tags (query_id, tag_id)
                    SELECT ?, id FROM tags WHERE name = ?
                """, (query_id, tag))

            return query_id

    def get_query(self, query_id: int) -> Optional[Query]:
        """Hent spørring med gitt ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM queries WHERE id = ?", (query_id,)
            ).fetchone()

            if not row:
                return None

            tags = [
                r[0] for r in conn.execute("""
                    SELECT t.name FROM tags t
                    JOIN query_tags qt ON t.id = qt.tag_id
                    WHERE qt.query_id = ?
                """, (query_id,)).fetchall()
            ]

            return Query(
                id=row["id"],
                question=row["question"],
                sql=row["sql"],
                result_summary=row["result_summary"],
                category=row["category"],
                tags=tags,
                verified_date=row["verified_date"],
                promoted=bool(row["promoted"]),
                notes=row["notes"],
            )

    def list_queries(
        self,
        category: Optional[str] = None,
        categories: Optional[list[str]] = None,
        exclude_categories: Optional[list[str]] = None,
        tag: Optional[str] = None,
        limit: int = 20,
    ) -> list[Query]:
        """
        List spørringer med valgfri filtrering.

        Args:
            category: Filtrer på én kategori (bakoverkompatibel)
            categories: Filtrer på flere kategorier (OR)
            exclude_categories: Ekskluder kategorier (NOT IN)
            tag: Filtrer på tag
            limit: Maks antall resultater (default 20)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            sql = "SELECT DISTINCT q.* FROM queries q"
            params = []

            if tag:
                sql += """
                    JOIN query_tags qt ON q.id = qt.query_id
                    JOIN tags t ON qt.tag_id = t.id
                """

            conditions = []

            # Støtt både enkelt category og liste med categories
            if category:
                conditions.append("LOWER(q.category) = LOWER(?)")
                params.append(category)
            elif categories:
                placeholders = ", ".join("?" for _ in categories)
                conditions.append(f"LOWER(q.category) IN ({placeholders})")
                params.extend([c.lower() for c in categories])

            # Ekskluder kategorier
            if exclude_categories:
                placeholders = ", ".join("?" for _ in exclude_categories)
                conditions.append(f"LOWER(q.category) NOT IN ({placeholders})")
                params.extend([c.lower() for c in exclude_categories])

            if tag:
                conditions.append("t.name = ?")
                params.append(tag)

            if conditions:
                sql += " WHERE " + " AND ".join(conditions)

            sql += " ORDER BY q.id DESC LIMIT ?"
            params.append(limit)

            rows = conn.execute(sql, params).fetchall()

            queries = []
            for row in rows:
                tags = [
                    r[0] for r in conn.execute("""
                        SELECT t.name FROM tags t
                        JOIN query_tags qt ON t.id = qt.tag_id
                        WHERE qt.query_id = ?
                    """, (row["id"],)).fetchall()
                ]
                queries.append(Query(
                    id=row["id"],
                    question=row["question"],
                    sql=row["sql"],
                    result_summary=row["result_summary"],
                    category=row["category"],
                    tags=tags,
                    verified_date=row["verified_date"],
                    promoted=bool(row["promoted"]),
                    notes=row["notes"],
                ))

            return queries

    def search_queries(self, search_term: str, limit: int = 10) -> list[Query]:
        """
        Søk i spørringer med FTS5.

        Støtter:
        - Enkle søkeord: "fiber"
        - Flere ord (implicit AND): "fiber spredtbygd"
        - Prefix-matching: "fiber*"
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            # FTS5 søk med BM25 ranking
            rows = conn.execute("""
                SELECT q.*, bm25(queries_fts) as rank
                FROM queries q
                JOIN queries_fts fts ON q.id = fts.rowid
                WHERE queries_fts MATCH ?
                ORDER BY rank
                LIMIT ?
            """, (search_term, limit)).fetchall()

            queries = []
            for row in rows:
                tags = [
                    r[0] for r in conn.execute("""
                        SELECT t.name FROM tags t
                        JOIN query_tags qt ON t.id = qt.tag_id
                        WHERE qt.query_id = ?
                    """, (row["id"],)).fetchall()
                ]
                queries.append(Query(
                    id=row["id"],
                    question=row["question"],
                    sql=row["sql"],
                    result_summary=row["result_summary"],
                    category=row["category"],
                    tags=tags,
                    verified_date=row["verified_date"],
                    promoted=bool(row["promoted"]),
                    notes=row["notes"],
                ))

            return queries

    def delete_query(self, query_id: int) -> bool:
        """Slett spørring."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM queries WHERE id = ?", (query_id,))
            return cursor.rowcount > 0

    # ========== Correction CRUD ==========

    def add_correction(
        self,
        context: str,
        error: str,
        solution: str,
        pattern: Optional[str] = None,
        created_date: Optional[str] = None,
    ) -> int:
        """Legg til ny korreksjon."""
        if created_date is None:
            created_date = datetime.now().strftime("%Y-%m-%d")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO corrections (context, error, solution, pattern, created_date)
                VALUES (?, ?, ?, ?, ?)
            """, (context, error, solution, pattern, created_date))
            return cursor.lastrowid

    def get_corrections(self, limit: int = 50) -> list[Correction]:
        """Hent alle korreksjoner."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM corrections ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()

            return [
                Correction(
                    id=row["id"],
                    context=row["context"],
                    error=row["error"],
                    solution=row["solution"],
                    created_date=row["created_date"],
                    pattern=row["pattern"],
                )
                for row in rows
            ]

    def find_matching_corrections(self, sql: str) -> list[Correction]:
        """Finn korreksjoner som matcher SQL (for pre-execution warnings)."""
        import re

        corrections = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM corrections WHERE pattern IS NOT NULL"
            ).fetchall()

            for row in rows:
                try:
                    if re.search(row["pattern"], sql, re.IGNORECASE):
                        corrections.append(Correction(
                            id=row["id"],
                            context=row["context"],
                            error=row["error"],
                            solution=row["solution"],
                            created_date=row["created_date"],
                            pattern=row["pattern"],
                        ))
                except re.error:
                    continue

        return corrections

    # ========== Backup/Export ==========

    def export_json(self, output_dir: Optional[Path] = None) -> tuple[Path, Path, Path]:
        """Eksporter til JSON og INDEX.md for backup."""
        output_dir = output_dir or BACKUP_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        queries_path = output_dir / "queries.json"
        corrections_path = output_dir / "corrections.json"
        index_path = output_dir / "INDEX.md"

        queries = self.list_queries(limit=1000)
        corrections = [c.to_dict() for c in self.get_corrections(limit=1000)]

        # JSON export
        with open(queries_path, "w", encoding="utf-8") as f:
            json.dump([q.to_dict() for q in queries], f, ensure_ascii=False, indent=2)

        with open(corrections_path, "w", encoding="utf-8") as f:
            json.dump(corrections, f, ensure_ascii=False, indent=2)

        # INDEX.md for rask lesing
        lines = ["| # | Kategori | Beskrivelse | Verifisert |",
                 "|---|----------|-------------|------------|"]
        for q in queries:
            desc = q.question[:45] + "..." if len(q.question) > 45 else q.question
            lines.append(f"| {q.id} | {q.category} | {desc} | {q.verified_date} |")

        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return queries_path, corrections_path, index_path

    def import_json(self, queries_path: Path, corrections_path: Optional[Path] = None):
        """Importer fra JSON backup."""
        with open(queries_path, encoding="utf-8") as f:
            queries = json.load(f)

        for q in queries:
            self.add_query(
                question=q["question"],
                sql=q["sql"],
                result_summary=q["result_summary"],
                category=q["category"],
                tags=q.get("tags", []),
                verified_date=q["verified_date"],
                promoted=q.get("promoted", False),
                notes=q.get("notes"),
            )

        if corrections_path and corrections_path.exists():
            with open(corrections_path, encoding="utf-8") as f:
                corrections = json.load(f)

            for c in corrections:
                self.add_correction(
                    context=c["context"],
                    error=c["error"],
                    solution=c["solution"],
                    pattern=c.get("pattern"),
                    created_date=c["created_date"],
                )

    # ========== Stats ==========

    def get_stats(self) -> dict:
        """Hent statistikk om kunnskapsbasen."""
        with sqlite3.connect(self.db_path) as conn:
            queries_count = conn.execute("SELECT COUNT(*) FROM queries").fetchone()[0]
            corrections_count = conn.execute("SELECT COUNT(*) FROM corrections").fetchone()[0]
            tags_count = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]

            categories = conn.execute("""
                SELECT category, COUNT(*) as count
                FROM queries
                GROUP BY category
                ORDER BY count DESC
            """).fetchall()

            return {
                "queries": queries_count,
                "corrections": corrections_count,
                "tags": tags_count,
                "categories": dict(categories),
            }


class SessionTracker:
    """
    Track queries under sesjon for batch-logging via /loggpush.

    I stedet for å logge hver spørring umiddelbart, husker SessionTracker
    dem til brukeren kjører /loggpush.

    Eksempel:
        from library import get_session

        session = get_session()
        session.remember_query("Fiberdekning?", "SELECT ...", "91% nasjonalt")
        # ... flere spørringer ...

        # Ved /loggpush:
        count = session.flush_to_kb(category="Dekning", tags=["fiber"])
    """

    def __init__(self):
        self._pending_queries: list[dict] = []
        self._pending_corrections: list[dict] = []

    def remember_query(
        self,
        question: str,
        sql: str,
        result_summary: str,
        category: str = "Dekning",
        tags: Optional[list[str]] = None,
    ):
        """Husk en verifisert spørring for senere logging."""
        self._pending_queries.append({
            "question": question,
            "sql": sql,
            "result_summary": result_summary,
            "category": category,
            "tags": tags or [],
        })

    def remember_correction(
        self,
        context: str,
        error: str,
        solution: str,
        pattern: Optional[str] = None,
    ):
        """Husk en korreksjon for senere logging."""
        self._pending_corrections.append({
            "context": context,
            "error": error,
            "solution": solution,
            "pattern": pattern,
        })

    def get_pending_count(self) -> tuple[int, int]:
        """Returner antall ventende (queries, corrections)."""
        return len(self._pending_queries), len(self._pending_corrections)

    def flush_to_kb(self) -> int:
        """
        Skriv alle ventende elementer til knowledge base.

        Returns:
            Antall elementer som ble skrevet
        """
        kb = KnowledgeBase()
        count = 0

        for q in self._pending_queries:
            kb.add_query(
                question=q["question"],
                sql=q["sql"],
                result_summary=q["result_summary"],
                category=q["category"],
                tags=q["tags"],
            )
            count += 1

        for c in self._pending_corrections:
            kb.add_correction(
                context=c["context"],
                error=c["error"],
                solution=c["solution"],
                pattern=c.get("pattern"),
            )
            count += 1

        self._pending_queries.clear()
        self._pending_corrections.clear()

        return count

    def clear(self):
        """Tøm ventende elementer uten å lagre."""
        self._pending_queries.clear()
        self._pending_corrections.clear()


# Singleton session tracker
_session: Optional[SessionTracker] = None


def get_session() -> SessionTracker:
    """
    Hent global SessionTracker instance.

    Returnerer samme instans gjennom hele sesjonen.
    """
    global _session
    if _session is None:
        _session = SessionTracker()
    return _session
