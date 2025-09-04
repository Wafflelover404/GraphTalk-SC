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

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, length_function=len)

embedding_function = SentenceTransformerEmbeddings(model_name="all-MiniLM-L6-v2")

vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embedding_function)

def load_and_split_document(file_path: str, filename: str) -> List[Document]:
	if file_path.endswith('.pdf'):
		loader = PyPDFLoader(file_path)
	elif file_path.endswith('.docx'):
		loader = Docx2txtLoader(file_path)
	elif file_path.endswith('.html'):
		loader = UnstructuredHTMLLoader(file_path)
	elif file_path.endswith('.txt') or file_path.endswith('.md'):
		# Handle .txt files by reading content and creating Document manually
		with open(file_path, 'r', encoding='utf-8') as f:
			content = f.read()
		document = Document(page_content=content, metadata={"source": file_path, "filename": filename})
		return text_splitter.split_documents([document])
	else:
		raise ValueError(f"Unsupported file type: {file_path}")

	documents = loader.load()
	# Add filename to metadata
	for doc in documents:
		doc.metadata["filename"] = filename
	return text_splitter.split_documents(documents)

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
