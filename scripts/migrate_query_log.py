#!/usr/bin/env python3
"""
Migrer QUERY_LOG.md til SQLite knowledge base.

Kjør: uv run python scripts/migrate_query_log.py
"""

import re
import sys
from pathlib import Path

# Legg til project root i path
sys.path.insert(0, str(Path(__file__).parent.parent))

from library.knowledge import KnowledgeBase


def parse_query_log(content: str) -> list[dict]:
    """Parse QUERY_LOG.md og ekstraher spørringer."""
    queries = []

    # Finn alle spørringer mellom Q:N markører
    pattern = r'<!-- Q:(\d+) -->\s*### ([^:]+):\s*([^\n]+)\s*\n\n\*\*Spørsmål:\*\*\s*"([^"]+)"[^\n]*\n\*\*Verifisert:\*\*\s*(\d{4}-\d{2}-\d{2})\s*\n\*\*Promotert:\*\*\s*(Ja|Nei)\s*\n\n```sql\n(.*?)```\s*\n\n\*\*Resultat:\*\*\s*([^\n]+)\s*\n\*\*Notater:\*\*\s*([^\n]+)?'

    for match in re.finditer(pattern, content, re.DOTALL):
        query_id = int(match.group(1))
        category = match.group(2).strip()
        title = match.group(3).strip()
        question = match.group(4).strip()
        verified_date = match.group(5).strip()
        promoted = match.group(6).strip() == "Ja"
        sql = match.group(7).strip()
        result = match.group(8).strip()
        notes = match.group(9).strip() if match.group(9) else None

        # Ekstraher tags fra tittel og kategori
        tags = extract_tags(category, title, sql)

        queries.append({
            "id": query_id,
            "category": category,
            "title": title,
            "question": question,
            "verified_date": verified_date,
            "promoted": promoted,
            "sql": sql,
            "result_summary": result,
            "notes": notes,
            "tags": tags,
        })

    return queries


def extract_tags(category: str, title: str, sql: str) -> list[str]:
    """Ekstraher tags fra innhold."""
    tags = []

    # Fra kategori
    category_lower = category.lower()
    if "dekning" in category_lower:
        tags.append("dekning")
    if "konkurranse" in category_lower:
        tags.append("konkurranse")
    if "historikk" in category_lower:
        tags.append("historikk")
    if "tilbyder" in category_lower:
        tags.append("tilbydere")
    if "abonnement" in category_lower:
        tags.append("abonnement")
    if "ekom" in category_lower:
        tags.append("ekom")

    # Fra tittel og SQL
    text = (title + " " + sql).lower()

    if "fiber" in text:
        tags.append("fiber")
    if "ftb" in text:
        tags.append("ftb")
    if "kabel" in text:
        tags.append("kabel")
    if "5g" in text:
        tags.append("5g")
    if "4g" in text:
        tags.append("4g")
    if "mobil" in text or "mob." in text:
        tags.append("mobil")

    if "spredtbygd" in text or "ertett = false" in text:
        tags.append("spredtbygd")
    if "tettsted" in text or "ertett = true" in text:
        tags.append("tettsted")

    if "fylke" in text:
        tags.append("fylke")
    if "kommune" in text:
        tags.append("kommune")

    if "hastighet" in text or "ned >=" in text or "mbit" in text:
        tags.append("hastighet")

    if "hc" in text or "homes connected" in text:
        tags.append("hc")

    if "fritid" in text or "fritidsbolig" in text:
        tags.append("fritidsboliger")

    if "tilbyder" in text or "tilb" in text:
        tags.append("tilbydere")

    if "kontantkort" in text:
        tags.append("kontantkort")

    return list(set(tags))


def migrate():
    """Kjør migrering."""
    # Les QUERY_LOG.md
    query_log_path = Path(__file__).parent.parent / "QUERY_LOG.md"

    if not query_log_path.exists():
        print(f"QUERY_LOG.md ikke funnet: {query_log_path}")
        return

    print(f"Leser {query_log_path}...")
    content = query_log_path.read_text(encoding="utf-8")

    # Parse
    print("Parser spørringer...")
    queries = parse_query_log(content)
    print(f"Fant {len(queries)} spørringer")

    if not queries:
        print("Ingen spørringer funnet! Sjekk parsing-logikk.")
        return

    # Opprett database
    print("Oppretter SQLite database...")
    kb = KnowledgeBase()

    # Migrer
    print("Migrerer spørringer...")
    for q in queries:
        print(f"  - Q:{q['id']}: {q['category']} - {q['title'][:50]}...")
        kb.add_query(
            question=q["question"],
            sql=q["sql"],
            result_summary=q["result_summary"],
            category=q["category"],
            tags=q["tags"],
            verified_date=q["verified_date"],
            promoted=q["promoted"],
            notes=q["notes"],
        )

    # Eksporter backup
    print("\nEksporterer JSON backup...")
    queries_path, corrections_path = kb.export_json()
    print(f"  - {queries_path}")
    print(f"  - {corrections_path}")

    # Statistikk
    stats = kb.get_stats()
    print(f"\nMigrering fullført!")
    print(f"  Spørringer: {stats['queries']}")
    print(f"  Tags: {stats['tags']}")
    print(f"  Kategorier: {stats['categories']}")


if __name__ == "__main__":
    migrate()
