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

        # Call LLM to generate quiz with retries for transient errors
        import asyncio
        attempts = 0
        max_attempts = 3
        last_err_text = None
        quiz_text = None
        while attempts < max_attempts:
            attempts += 1
            try:
                quiz_text = await llm_call(
                    message=instruction,
                    data=content_snippet
                )
                # If API occasionally returns stringified error, detect common overload status
                if isinstance(quiz_text, str) and ("UNAVAILABLE" in quiz_text or "503" in quiz_text):
                    last_err_text = quiz_text
                    # Backoff then retry
                    await asyncio.sleep(2 * attempts)
                    continue
                break
            except Exception as e:
                last_err_text = str(e)
                await asyncio.sleep(2 * attempts)

        # Try to ensure it's JSON. Handle cases where LLM returns fenced ```json blocks.
        quiz_json_str: str
        try:
            # If response contains a fenced JSON block, extract it
            if isinstance(quiz_text, str):
                import re
                m = re.search(r"```json\s*(\{.*?\})\s*```", quiz_text, re.DOTALL)
                if m:
                    quiz_text_to_parse = m.group(1)
                else:
                    # try generic fenced block
                    m2 = re.search(r"```[a-zA-Z]*\s*(\{.*?\})\s*```", quiz_text, re.DOTALL)
                    quiz_text_to_parse = m2.group(1) if m2 else quiz_text
            else:
                quiz_text_to_parse = quiz_text

            parsed = json.loads(quiz_text_to_parse)
            # Normalize to ensure correct keys exist
            if isinstance(parsed, dict) and 'questions' in parsed:
                quiz_json_str = json.dumps(parsed, ensure_ascii=False)
            else:
                # Fallback wrap
                quiz_json_str = json.dumps({"questions": [], "raw": quiz_text, "_attempts": attempts, "_error": last_err_text}, ensure_ascii=False)
        except Exception:
            quiz_json_str = json.dumps({"questions": [], "raw": quiz_text, "_attempts": attempts, "_error": last_err_text}, ensure_ascii=False)

        logs_txt = None
        if last_err_text:
            logs_txt = f"llm_attempts={attempts}, last_error={last_err_text[:500]}"
        quiz_id = await insert_quiz_record(source_filename=source_filename, quiz_json=quiz_json_str, logs=logs_txt)
        return quiz_id
    except Exception as e:
        # Store failure log row to help debugging
        try:
            await insert_quiz_record(source_filename=source_filename, quiz_json=json.dumps({"questions": []}, ensure_ascii=False), logs=str(e))
        except Exception:
            pass
        return None

