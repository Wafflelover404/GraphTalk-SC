import os
import sqlite3
from rag_api.chroma_utils import delete_doc_from_chroma, index_document_to_chroma

def get_db_connection():
    conn = sqlite3.connect("rag_app.db")
    conn.row_factory = sqlite3.Row
    return conn

def reindex_all_documents():
    """Reindex all documents in Chroma with proper filename metadata"""
    try:
        # Get all documents from the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, content FROM document_store")
        documents = cursor.fetchall()
        conn.close()

        success_count = 0
        fail_count = 0

        for doc in documents:
            file_id = doc['id']
            filename = doc['filename']
            content = doc['content']

            # Create a temporary file to reindex
            temp_file_path = f"temp_{filename}"
            try:
                # Write content to temp file
                with open(temp_file_path, "wb") as f:
                    f.write(content)

                # Delete existing document from Chroma
                delete_doc_from_chroma(file_id)

                # Reindex with proper filename metadata
                if index_document_to_chroma(temp_file_path, file_id):
                    success_count += 1
                    print(f"Successfully reindexed {filename} (ID: {file_id})")
                else:
                    fail_count += 1
                    print(f"Failed to reindex {filename} (ID: {file_id})")

            except Exception as e:
                fail_count += 1
                print(f"Error reindexing {filename} (ID: {file_id}): {e}")
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "total": len(documents)
        }

    except Exception as e:
        print(f"Error during reindexing: {e}")
        return {
            "success_count": 0,
            "fail_count": 0,
            "total": 0,
            "error": str(e)
        }

if __name__ == "__main__":
    print("Starting reindexing of all documents...")
    results = reindex_all_documents()
    print(f"\nReindexing complete:")
    print(f"Total documents: {results['total']}")
    print(f"Successfully reindexed: {results['success_count']}")
    print(f"Failed to reindex: {results['fail_count']}")
    if 'error' in results:
        print(f"Error: {results['error']}")
