import sqlite3
from datetime import datetime

DB_NAME = "rag_app.db"

def get_db_connection():
	conn = sqlite3.connect(DB_NAME)
	conn.row_factory = sqlite3.Row
	return conn

def create_application_logs():
    conn = get_db_connection()
    # Drop the existing table if it exists to recreate it with the correct schema
    conn.execute('''DROP TABLE IF EXISTS application_logs''')
    # Recreate the table with NOT NULL constraint on session_id
    conn.execute('''CREATE TABLE application_logs
                    (id INTEGER PRIMARY KEY AUTOINCREMENT,
                     session_id TEXT NOT NULL,
                     user_query TEXT,
                     gpt_response TEXT,
                     model TEXT,
                     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def create_document_store():
	conn = get_db_connection()
	conn.execute('''CREATE TABLE IF NOT EXISTS document_store
				   (id INTEGER PRIMARY KEY AUTOINCREMENT,
					filename TEXT,
					content BLOB,
					upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
	conn.close()

def insert_application_logs(session_id, user_query, gpt_response, model):
	conn = get_db_connection()
	conn.execute('INSERT INTO application_logs (session_id, user_query, gpt_response, model) VALUES (?, ?, ?, ?)',
				 (session_id, user_query, gpt_response, model))
	conn.commit()
	conn.close()

def get_chat_history(session_id):
	conn = get_db_connection()
	cursor = conn.cursor()
	cursor.execute('SELECT user_query, gpt_response FROM application_logs WHERE session_id = ? ORDER BY created_at', (session_id,))
	messages = []
	for row in cursor.fetchall():
		messages.extend([
			{"role": "human", "content": row['user_query']},
			{"role": "ai", "content": row['gpt_response']}
		])
	conn.close()
	return messages

def insert_document_record(filename, content_bytes):
	conn = get_db_connection()
	cursor = conn.cursor()
	cursor.execute('INSERT INTO document_store (filename, content) VALUES (?, ?)', (filename, content_bytes))
	file_id = cursor.lastrowid
	conn.commit()
	conn.close()
	return file_id
def get_file_content_by_filename(filename):
	conn = get_db_connection()
	cursor = conn.cursor()
	cursor.execute('SELECT content FROM document_store WHERE filename = ?', (filename,))
	row = cursor.fetchone()
	conn.close()
	if row:
		return row['content']
	return None

def delete_document_record(file_id):
	conn = get_db_connection()
	conn.execute('DELETE FROM document_store WHERE id = ?', (file_id,))
	conn.commit()
	conn.close()
	return True

def get_all_documents():
	conn = get_db_connection()
	cursor = conn.cursor()
	cursor.execute('SELECT id, filename, upload_timestamp FROM document_store ORDER BY upload_timestamp DESC')
	documents = cursor.fetchall()
	conn.close()
	return [dict(doc) for doc in documents]

def update_document_record(filename, new_content_bytes):
	conn = get_db_connection()
	cursor = conn.cursor()
	cursor.execute('SELECT id FROM document_store WHERE filename = ?', (filename,))
	rows = cursor.fetchall()
	if not rows:
		conn.close()
		return []
	file_ids = [row['id'] for row in rows]
	cursor.execute('UPDATE document_store SET content = ? WHERE filename = ?', (new_content_bytes, filename))
	conn.commit()
	conn.close()
	return file_ids

create_application_logs()
create_document_store()
