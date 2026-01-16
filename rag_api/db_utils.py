import sqlite3
from datetime import datetime

DB_NAME = "rag_app.db"

def get_db_connection():
	conn = sqlite3.connect(DB_NAME)
	# Enable UTF-8 support for database
	conn.execute("PRAGMA encoding='UTF-8'")
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
					upload_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
					organization_id TEXT)''')
	# Backfill columns if missing
	try:
		cursor = conn.execute("PRAGMA table_info(document_store)")
		cols = {row[1] for row in cursor.fetchall()}
		if "organization_id" not in cols:
			conn.execute("ALTER TABLE document_store ADD COLUMN organization_id TEXT")
		if "file_size" not in cols:
			conn.execute("ALTER TABLE document_store ADD COLUMN file_size INTEGER")
		conn.commit()
	except Exception:
		pass
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

def insert_document_record(filename, content_bytes=None, organization_id=None):
	conn = get_db_connection()
	cursor = conn.cursor()
	# Ensure filename is properly encoded as UTF-8
	if isinstance(filename, bytes):
		filename = filename.decode('utf-8', errors='replace')
	if content_bytes is None:
		content_bytes = b""
	file_size = len(content_bytes)
	cursor.execute(
		'INSERT INTO document_store (filename, content, organization_id, file_size) VALUES (?, ?, ?, ?)',
		(filename, content_bytes, organization_id, file_size)
	)
	file_id = cursor.lastrowid
	conn.commit()
	conn.close()
	return file_id
def get_file_content_by_filename(filename, organization_id=None):
	conn = get_db_connection()
	cursor = conn.cursor()
	# Ensure filename is properly encoded as UTF-8
	if isinstance(filename, bytes):
		filename = filename.decode('utf-8', errors='replace')
	if organization_id:
		cursor.execute('SELECT content FROM document_store WHERE filename = ? AND organization_id = ?', (filename, organization_id))
	else:
		cursor.execute('SELECT content FROM document_store WHERE filename = ?', (filename,))
	row = cursor.fetchone()
	conn.close()
	if row:
		return row['content']
	return None

def delete_document_record(file_id):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Check if document exists first
        cursor.execute('SELECT id FROM document_store WHERE id = ?', (file_id,))
        exists = cursor.fetchone()
        
        if not exists:
            print(f"No document found with file_id {file_id} in database")
            conn.close()
            return True  # Consider successful if nothing to delete
        
        # Delete the document
        cursor.execute('DELETE FROM document_store WHERE id = ?', (file_id,))
        conn.commit()
        conn.close()
        print(f"Successfully deleted document with file_id {file_id} from database")
        return True
    except Exception as e:
        print(f"Error deleting document record with file_id {file_id}: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_all_documents(organization_id=None):
	conn = get_db_connection()
	cursor = conn.cursor()
	if organization_id:
		cursor.execute(
			'SELECT id, filename, upload_timestamp, organization_id, file_size FROM document_store WHERE organization_id = ? ORDER BY upload_timestamp DESC',
			(organization_id,)
		)
	else:
		cursor.execute('SELECT id, filename, upload_timestamp, organization_id, file_size FROM document_store ORDER BY upload_timestamp DESC')
	documents = cursor.fetchall()
	conn.close()
	return [dict(doc) for doc in documents]

def update_document_record(filename, new_content_bytes, organization_id=None):
	conn = get_db_connection()
	cursor = conn.cursor()
	# Ensure filename is properly encoded as UTF-8
	if isinstance(filename, bytes):
		filename = filename.decode('utf-8', errors='replace')
	if new_content_bytes is None:
		new_content_bytes = b""
	file_size = len(new_content_bytes)
	if organization_id:
		cursor.execute('SELECT id FROM document_store WHERE filename = ? AND organization_id = ?', (filename, organization_id))
	else:
		cursor.execute('SELECT id FROM document_store WHERE filename = ?', (filename,))
	rows = cursor.fetchall()
	if not rows:
		conn.close()
		return []
	file_ids = [row['id'] for row in rows]
	if organization_id:
		cursor.execute('UPDATE document_store SET content = ?, file_size = ? WHERE filename = ? AND organization_id = ?', (new_content_bytes, file_size, filename, organization_id))
	else:
		cursor.execute('UPDATE document_store SET content = ?, file_size = ? WHERE filename = ?', (new_content_bytes, file_size, filename))
	conn.commit()
	conn.close()
	return file_ids

create_application_logs()
create_document_store()
