import aiosqlite
import os
import uuid
import json
import datetime
from typing import Optional, Tuple

from rag_api.db_utils import get_file_content_by_filename
from llm import llm_call

DB_PATH = os.path.join(os.path.dirname(__file__), 'quiz.db')

async def init_quiz_db():
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS quizes (
                id TEXT PRIMARY KEY,
                source_filename TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                quiz_json TEXT NOT NULL,
                logs TEXT
            )
        ''')
        # Detect legacy schema with 'json-content' and migrate
        try:
            async with conn.execute("PRAGMA table_info(quizes)") as cursor:
                cols = await cursor.fetchall()
                col_names = {c[1] for c in cols}
            if 'quiz_json' not in col_names:
                # Legacy table likely exists; create new table and copy
                await conn.execute('''
                    CREATE TABLE IF NOT EXISTS quizes_new (
                        id TEXT PRIMARY KEY,
                        source_filename TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        quiz_json TEXT NOT NULL,
                        logs TEXT
                    )
                ''')
                # Try to copy from legacy column name if present
                legacy_has_json_dash = 'json-content' in col_names
                if legacy_has_json_dash:
                    await conn.execute('''
                        INSERT INTO quizes_new (id, source_filename, timestamp, quiz_json, logs)
                        SELECT id, source_filename, timestamp, "json-content", logs FROM quizes
                    ''')
                else:
                    # No recognizable content column; copy available fields with empty quiz_json
                    await conn.execute('''
                        INSERT INTO quizes_new (id, source_filename, timestamp, quiz_json, logs)
                        SELECT id, source_filename, timestamp, '' as quiz_json, logs FROM quizes
                    ''')
                await conn.execute('DROP TABLE quizes')
                await conn.execute('ALTER TABLE quizes_new RENAME TO quizes')
        except Exception:
            # If PRAGMA fails or migration errors, proceed without blocking app start
            pass
        await conn.commit()


async def insert_quiz_record(source_filename: str, quiz_json: str, logs: Optional[str] = None) -> str:
    """Insert a quiz record and return its id."""
    quiz_id = str(uuid.uuid4())
    timestamp = datetime.datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as conn:
        await conn.execute(
            'INSERT INTO quizes (id, source_filename, timestamp, quiz_json, logs) VALUES (?, ?, ?, ?, ?)',
            (quiz_id, source_filename, timestamp, quiz_json, logs)
        )
        await conn.commit()
    return quiz_id


async def get_quiz_by_filename(source_filename: str) -> Optional[Tuple[str, str, str, str, Optional[str]]]:
    """Return row for a given filename: (id, source_filename, timestamp, quiz_json, logs) or None."""
    async with aiosqlite.connect(DB_PATH) as conn:
        async with conn.execute(
            'SELECT id, source_filename, timestamp, quiz_json, logs FROM quizes WHERE source_filename = ? ORDER BY timestamp DESC LIMIT 1',
            (source_filename,)
        ) as cursor:
            row = await cursor.fetchone()
            return row if row else None


async def create_quiz_for_filename(source_filename: str) -> Optional[str]:
    """
    Generate a quiz for the given file (stored in DB) and save it into the quiz DB.
    The quiz is generated in the same language as the document.

    Returns the quiz_id if created, otherwise None.
    """
    try:
        content_bytes = get_file_content_by_filename(source_filename)
        if content_bytes is None:
            # File not found in DB
            return None

        # Try decoding content
        try:
            content = content_bytes.decode('utf-8')
        except UnicodeDecodeError:
            try:
                content = content_bytes.decode('latin1')
            except Exception:
                # As a last resort, replace errors
                content = content_bytes.decode('utf-8', errors='replace')

        # Limit content length to keep under model limits
        max_chars = 12000
        if len(content) > max_chars:
            content_snippet = content[:max_chars]
        else:
            content_snippet = content

        # Build instruction for LLM
        instruction = (
            "You are a quiz generator. Read the document content and create a short quiz "
            "to help users remember it better. Respond ONLY with valid JSON. The JSON MUST be in the same language as the document. "
            "Structure strictly as: {\n"
            "  \"questions\": [\n"
            "    { \"question\": string, \"options\": [string, string, string, string], \"answer\": string }\n"
            "  ]\n"
            "}.\n"
            "Rules: 3-8 questions; each has 3-5 plausible options; ensure exactly one correct answer; keep content faithful to the document."
        )

        # Call LLM to generate quiz
        quiz_text = await llm_call(
            message=instruction,
            data=content_snippet
        )

        # Try to ensure it's JSON. If not, wrap as text under a key.
        quiz_json_str: str
        try:
            parsed = json.loads(quiz_text)
            # Normalize to ensure correct keys exist
            if isinstance(parsed, dict) and 'questions' in parsed:
                quiz_json_str = json.dumps(parsed, ensure_ascii=False)
            else:
                # Fallback wrap
                quiz_json_str = json.dumps({"questions": [], "raw": quiz_text}, ensure_ascii=False)
        except Exception:
            quiz_json_str = json.dumps({"questions": [], "raw": quiz_text}, ensure_ascii=False)

        quiz_id = await insert_quiz_record(source_filename=source_filename, quiz_json=quiz_json_str, logs=None)
        return quiz_id
    except Exception as e:
        # Store failure log row to help debugging
        try:
            await insert_quiz_record(source_filename=source_filename, quiz_json=json.dumps({"questions": []}, ensure_ascii=False), logs=str(e))
        except Exception:
            pass
        return None

