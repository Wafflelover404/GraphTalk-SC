import os
import sqlite3
import time
from datetime import datetime
from rag_api.chroma_utils import delete_doc_from_chroma, index_document_to_chroma

def get_db_connection():
    conn = sqlite3.connect("rag_app.db")
    conn.row_factory = sqlite3.Row
    return conn

def reindex_all_documents():
    """
    Reindex all documents in Chroma with enhanced Chonkie chunking.
    Uses intelligent chunker selection and improved metadata.
    """
    import shutil
    
    print("=" * 70)
    print("Enhanced Document Reindexing with Chonkie")
    print("=" * 70)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    # Clean up old Chroma DB
    if os.path.exists("./chroma_db"):
        print("🗑️  Removing old Chroma database...")
        shutil.rmtree("./chroma_db")
        print("✓ Old database removed\n")
    
    try:
        # Get all documents from the database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, filename, content FROM document_store")
        documents = cursor.fetchall()
        conn.close()

        total_docs = len(documents)
        print(f"📚 Found {total_docs} documents to reindex\n")

        success_count = 0
        fail_count = 0
        start_time = time.time()

        for idx, doc in enumerate(documents, 1):
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

                # Reindex with enhanced Chonkie chunking
                if index_document_to_chroma(temp_file_path, file_id):
                    success_count += 1
                    progress = (idx / total_docs) * 100
                    print(f"[{idx}/{total_docs}] ({progress:.1f}%) ✓ {filename}")
                else:
                    fail_count += 1
                    print(f"[{idx}/{total_docs}] ✗ Failed: {filename}")

            except Exception as e:
                fail_count += 1
                print(f"[{idx}/{total_docs}] ✗ Error: {filename} - {str(e)[:50]}")
            finally:
                # Clean up temp file
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)

        elapsed_time = time.time() - start_time
        
        return {
            "success_count": success_count,
            "fail_count": fail_count,
            "total": len(documents),
            "elapsed_time": elapsed_time
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
    results = reindex_all_documents()
    
    print("\n" + "=" * 70)
    print("Reindexing Summary")
    print("=" * 70)
    print(f"Total documents:      {results['total']}")
    print(f"✓ Successfully indexed: {results['success_count']}")
    print(f"✗ Failed:              {results['fail_count']}")
    
    if 'elapsed_time' in results:
        elapsed = results['elapsed_time']
        print(f"⏱️  Time elapsed:       {elapsed:.2f} seconds")
        if results['total'] > 0:
            avg_time = elapsed / results['total']
            print(f"📊 Average per doc:    {avg_time:.2f} seconds")
    
    if 'error' in results:
        print(f"\n❌ Error: {results['error']}")
    elif results['fail_count'] == 0:
        print("\n🎉 All documents reindexed successfully!")
    else:
        print(f"\n⚠️  {results['fail_count']} document(s) failed to reindex")
    
    print("=" * 70)
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
