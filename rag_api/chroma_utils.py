import os
from langchain_community.document_loaders import PyPDFLoader, Docx2txtLoader, UnstructuredHTMLLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
try:
    from langchain_huggingface import HuggingFaceEmbeddings as SentenceTransformerEmbeddings
except ImportError:
    from langchain_community.embeddings.sentence_transformer import SentenceTransformerEmbeddings
from langchain_chroma import Chroma
from typing import List
from langchain_core.documents import Document

text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1500,  # Increased chunk size for more context
    chunk_overlap=300,  # Increased overlap to maintain context between chunks
    length_function=len,
    separators=["\n\n", "\n", " ", ""]  # More granular separation
)

embedding_function = SentenceTransformerEmbeddings(
    model_name="Qwen/Qwen3-Embedding-0.6B",  # More capable model for better embeddings
    model_kwargs={"device": "cpu"}
)

# Create a fresh Chroma instance with explicit dimensions
vectorstore = Chroma(
    persist_directory="./chroma_db",
    collection_name="documents_qwen",  # New collection name to force recreation
    embedding_function=embedding_function,
    collection_metadata={"hnsw:space": "cosine"}  # Add metadata to ensure new collection
)

def load_and_split_document(file_path: str, filename: str) -> List[Document]:
    """Load and split document with enhanced metadata and preprocessing"""
    try:
        if file_path.endswith('.pdf'):
            loader = PyPDFLoader(file_path)
        elif file_path.endswith('.docx'):
            loader = Docx2txtLoader(file_path)
        elif file_path.endswith('.html'):
            loader = UnstructuredHTMLLoader(file_path)
        elif file_path.endswith('.txt') or file_path.endswith('.md'):
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Preprocess content to improve quality
            content = preprocess_text(content)
            
            document = Document(
                page_content=content, 
                metadata={
                    "source": file_path,
                    "filename": filename,
                    "file_type": os.path.splitext(filename)[1],
                    "created_at": os.path.getctime(file_path),
                    "modified_at": os.path.getmtime(file_path)
                }
            )
            return text_splitter.split_documents([document])
        else:
            raise ValueError(f"Unsupported file type: {file_path}")

        documents = loader.load()
        
        # Enhanced metadata for all documents
        for doc in documents:
            doc.metadata.update({
                "filename": filename,
                "file_type": os.path.splitext(filename)[1],
                "created_at": os.path.getctime(file_path),
                "modified_at": os.path.getmtime(file_path)
            })
            
            # Preprocess content to improve quality
            doc.page_content = preprocess_text(doc.page_content)
            
        return text_splitter.split_documents(documents)
        
    except Exception as e:
        print(f"Error loading document {filename}: {str(e)}")
        raise

def preprocess_text(text: str) -> str:
    """Preprocess text to improve quality of embeddings"""
    import re
    
    # Remove multiple newlines and whitespace
    text = re.sub(r'\n\s*\n', '\n\n', text)
    text = re.sub(r'\s+', ' ', text)
    
    # Remove special characters but keep essential punctuation
    text = re.sub(r'[^\w\s.,!?;:\-\'\"%()\[\]{}]', ' ', text)
    
    # Normalize whitespace
    text = ' '.join(text.split())
    
    return text.strip()

def index_document_to_chroma(file_path: str, file_id: int) -> bool:
	try:
		# Extract just the filename from the path
		filename = os.path.basename(file_path)
		splits = load_and_split_document(file_path, filename)
		for split in splits:
			split.metadata['file_id'] = file_id
			split.metadata['filename'] = filename  # Ensure filename is in metadata
		vectorstore.add_documents(splits)
		return True
	except Exception as e:
		print(f"Error indexing document: {e}")
		return False

def delete_doc_from_chroma(file_id: int):
	try:
		docs = vectorstore.get(where={"file_id": file_id})
		print(f"Found {len(docs['ids'])} document chunks for file_id {file_id}")

		vectorstore._collection.delete(where={"file_id": file_id})
		print(f"Deleted all documents with file_id {file_id}")

		return True
	except Exception as e:
		print(f"Error deleting document with file_id {file_id} from Chroma: {str(e)}")
		return False
