"""
Test suite for multi-format document support including ZIP archives.
"""

import os
import sys
import tempfile
import zipfile
import json
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_api.chroma_utils import load_and_split_document, index_document_to_chroma
from rag_api.document_loaders import ZIPLoader, EnhancedPDFLoader, EnhancedDocxLoader


def create_test_text_file(temp_dir, filename, content):
    """Create a test text file."""
    filepath = os.path.join(temp_dir, filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    return filepath


def create_test_zip_with_documents(temp_dir, zip_filename, documents):
    """
    Create a test ZIP file containing multiple documents.
    
    Args:
        temp_dir: Temporary directory to create ZIP in
        zip_filename: Name of the ZIP file to create
        documents: Dict of {filename: content} pairs
    
    Returns:
        Path to the created ZIP file
    """
    zip_path = os.path.join(temp_dir, zip_filename)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for filename, content in documents.items():
            zipf.writestr(filename, content)
    
    return zip_path


def test_text_file_loading():
    """Test loading and processing of text files."""
    print("\n=== Test 1: Text File Loading ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test file
        test_content = """
        This is a test document.
        It contains multiple paragraphs.
        
        This paragraph has some important information.
        The system should chunk this appropriately.
        """
        
        filepath = create_test_text_file(temp_dir, "test.txt", test_content)
        
        try:
            documents = load_and_split_document(filepath, "test.txt")
            print(f"✓ Successfully loaded text file")
            print(f"  - Generated {len(documents)} chunks")
            
            # Verify metadata
            for i, doc in enumerate(documents):
                assert 'filename' in doc.metadata, "Missing filename in metadata"
                assert 'file_type' in doc.metadata, "Missing file_type in metadata"
                assert doc.metadata['filename'] == 'test.txt', "Incorrect filename in metadata"
                assert doc.metadata['file_type'] == '.txt', "Incorrect file_type in metadata"
                print(f"  - Chunk {i+1}: {len(doc.page_content)} chars")
            
            print("✓ All metadata checks passed")
            return True
        except Exception as e:
            print(f"✗ Failed to load text file: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_zip_file_extraction():
    """Test ZIP file extraction and processing."""
    print("\n=== Test 2: ZIP File Extraction ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test documents to include in ZIP
        documents = {
            'document1.txt': 'This is the first document in the ZIP archive.\nIt has multiple lines.\n',
            'document2.txt': 'This is the second document.\nAlso with multiple lines.\n',
            'subdir/document3.txt': 'This document is in a subdirectory.\nBut should still be extracted.\n'
        }
        
        zip_path = create_test_zip_with_documents(temp_dir, "test_archive.zip", documents)
        
        try:
            # Test ZIPLoader directly
            loader = ZIPLoader(zip_path, allowed_extensions=['.txt'])
            loaded_docs = loader.load()
            
            print(f"✓ Successfully extracted ZIP file")
            print(f"  - Extracted {len(loaded_docs)} documents")
            
            # Verify archive metadata
            for doc in loaded_docs:
                assert 'archive_source' in doc.metadata, "Missing archive_source in metadata"
                assert 'archive_path' in doc.metadata, "Missing archive_path in metadata"
                assert doc.metadata['archive_source'] == zip_path, "Incorrect archive_source"
                print(f"  - {doc.metadata['archive_path']}: {len(doc.page_content)} chars")
            
            print("✓ All ZIP extraction checks passed")
            return True
        except Exception as e:
            print(f"✗ Failed to extract ZIP: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_zip_file_chunking():
    """Test that ZIP-extracted documents are properly chunked."""
    print("\n=== Test 3: ZIP File Chunking ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create test documents
        long_content = "This is a test paragraph. " * 50  # Repeat to create longer content
        documents = {
            'long_document.txt': long_content
        }
        
        zip_path = create_test_zip_with_documents(temp_dir, "test_chunks.zip", documents)
        
        try:
            # Load and split the ZIP
            chunked_docs = load_and_split_document(zip_path, "test_chunks.zip")
            
            print(f"✓ Successfully chunked ZIP file contents")
            print(f"  - Generated {len(chunked_docs)} chunks from ZIP")
            
            # Verify chunking metadata
            for i, doc in enumerate(chunked_docs):
                assert 'archive_source' in doc.metadata, "Missing archive_source in chunked doc"
                assert 'archive_path' in doc.metadata, "Missing archive_path in chunked doc"
                assert 'chunk_start' in doc.metadata, "Missing chunk_start"
                assert 'chunk_end' in doc.metadata, "Missing chunk_end"
                assert 'token_count' in doc.metadata, "Missing token_count"
                print(f"  - Chunk {i+1}: tokens={doc.metadata.get('token_count', 'N/A')}, "
                      f"archive_path={doc.metadata['archive_path']}")
            
            print("✓ All chunking checks passed")
            return True
        except Exception as e:
            print(f"✗ Failed to chunk ZIP contents: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_mixed_file_types_in_zip():
    """Test ZIP containing mixed file types."""
    print("\n=== Test 4: Mixed File Types in ZIP ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create mixed content
        documents = {
            'readme.txt': 'This is a README file.\nContains important information.\n',
            'notes.md': '# Notes\n## Section 1\nSome markdown content.\n',
            'data.html': '<html><body><p>HTML content here</p></body></html>\n'
        }
        
        zip_path = create_test_zip_with_documents(temp_dir, "mixed.zip", documents)
        
        try:
            # Load with multiple extension support
            loader = ZIPLoader(
                zip_path,
                allowed_extensions=['.txt', '.md', '.html'],
                max_files=10
            )
            loaded_docs = loader.load()
            
            print(f"✓ Successfully processed mixed file types")
            print(f"  - Loaded {len(loaded_docs)} documents from ZIP")
            
            # Count by extension
            extensions = {}
            for doc in loaded_docs:
                archive_path = doc.metadata.get('archive_path', 'unknown')
                ext = os.path.splitext(archive_path)[1]
                extensions[ext] = extensions.get(ext, 0) + 1
                print(f"  - {archive_path} ({ext}): {len(doc.page_content)} chars")
            
            print(f"✓ File type distribution: {extensions}")
            print("✓ All mixed-type checks passed")
            return True
        except Exception as e:
            print(f"✗ Failed to process mixed types: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_file_type_validation():
    """Test that file type validation works correctly."""
    print("\n=== Test 5: File Type Validation ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Try to load unsupported file type
        documents = {
            'unsupported.xyz': 'This should be filtered out',
            'readme.txt': 'This should be loaded'
        }
        
        zip_path = create_test_zip_with_documents(temp_dir, "filtered.zip", documents)
        
        try:
            loader = ZIPLoader(zip_path, allowed_extensions=['.txt', '.md'])
            loaded_docs = loader.load()
            
            # Should only have txt file
            assert len(loaded_docs) == 1, f"Expected 1 doc, got {len(loaded_docs)}"
            assert 'readme.txt' in loaded_docs[0].metadata['archive_path'], "Wrong file loaded"
            
            print(f"✓ File type filtering works correctly")
            print(f"  - Filtered unsupported files")
            print(f"  - Loaded only allowed extensions")
            return True
        except Exception as e:
            print(f"✗ File type validation failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def test_metadata_preservation():
    """Test that metadata is properly preserved through the pipeline."""
    print("\n=== Test 6: Metadata Preservation ===")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        documents = {
            'test.txt': 'Test content for metadata preservation.\n' * 20
        }
        
        zip_path = create_test_zip_with_documents(temp_dir, "metadata.zip", documents)
        
        try:
            chunked_docs = load_and_split_document(zip_path, "metadata.zip")
            
            print(f"✓ Generated {len(chunked_docs)} chunks with metadata")
            
            required_fields = [
                'filename', 'file_type', 'archive_source', 'archive_path',
                'chunk_start', 'chunk_end', 'token_count'
            ]
            
            for doc in chunked_docs:
                for field in required_fields:
                    assert field in doc.metadata, f"Missing field: {field}"
            
            print(f"✓ All required metadata fields present:")
            for field in required_fields:
                print(f"    - {field}")
            
            return True
        except Exception as e:
            print(f"✗ Metadata preservation failed: {e}")
            import traceback
            traceback.print_exc()
            return False


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "="*60)
    print("MULTI-FORMAT DOCUMENT SUPPORT TEST SUITE")
    print("="*60)
    
    tests = [
        ("Text File Loading", test_text_file_loading),
        ("ZIP File Extraction", test_zip_file_extraction),
        ("ZIP File Chunking", test_zip_file_chunking),
        ("Mixed File Types in ZIP", test_mixed_file_types_in_zip),
        ("File Type Validation", test_file_type_validation),
        ("Metadata Preservation", test_metadata_preservation),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n✗ Unexpected error in {test_name}: {e}")
            import traceback
            traceback.print_exc()
            results.append((test_name, False))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print("="*60)
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
