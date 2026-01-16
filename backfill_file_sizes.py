#!/usr/bin/env python3
"""
Script to backfill file sizes for existing documents that don't have file_size set
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'rag_app.db')

def backfill_file_sizes():
    """Update file_size for existing documents based on content length"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all documents where file_size is NULL or 0
    cursor.execute('SELECT id, filename, content FROM document_store WHERE file_size IS NULL OR file_size = 0')
    documents = cursor.fetchall()
    
    print(f"Found {len(documents)} documents needing file size update")
    
    updated_count = 0
    for doc_id, filename, content in documents:
        if content:
            file_size = len(content)
            cursor.execute('UPDATE document_store SET file_size = ? WHERE id = ?', (file_size, doc_id))
            updated_count += 1
            print(f"Updated {filename}: {file_size} bytes")
        else:
            cursor.execute('UPDATE document_store SET file_size = 0 WHERE id = ?', (doc_id,))
            print(f"Set {filename}: 0 bytes (no content)")
    
    conn.commit()
    conn.close()
    print(f"✅ Updated file sizes for {updated_count} documents")

if __name__ == "__main__":
    backfill_file_sizes()
