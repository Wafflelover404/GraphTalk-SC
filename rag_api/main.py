from fastapi import FastAPI, File, UploadFile, HTTPException
from pydantic_models import QueryInput, QueryResponse, DocumentInfo, DeleteFileRequest
from langchain_utils import get_rag_chain
from db_utils import insert_application_logs, get_chat_history, get_all_documents, insert_document_record, delete_document_record
from chroma_utils import index_document_to_chroma, delete_doc_from_chroma
import os
import uuid
import logging
import shutil

logging.basicConfig(filename='app.log', level=logging.INFO)

app = FastAPI()

@app.post("/chat", response_model=QueryResponse)
def chat(query_input: QueryInput):
	session_id = query_input.session_id or str(uuid.uuid4())
	logging.info(f"Session ID: {session_id}, User Query: {query_input.question}, , Model: {query_input.model.value}")
    
	chat_history = get_chat_history(session_id)
	rag_chain = get_rag_chain(query_input.model.value)
	answer = rag_chain.invoke({
		"input": query_input.question,
		"chat_history": chat_history
	})['answer']

	insert_application_logs(session_id, query_input.question, answer, query_input.model.value)
	logging.info(f"Session ID: {session_id}, AI Response: {answer}")
	return QueryResponse(answer=answer, session_id=session_id, model=query_input.model)


@app.post("/upload-doc")
def upload_and_index_document(file: UploadFile = File(...)):
	# Extended support for PDF, DOCX, DOC, HTML, TXT, MD, and ZIP archives
	allowed_extensions = ['.pdf', '.docx', '.doc', '.html', '.txt', '.md', '.zip']
	file_extension = os.path.splitext(file.filename)[1].lower()

	if file_extension not in allowed_extensions:
		raise HTTPException(status_code=400, detail=f"Unsupported file type. Allowed types are: {', '.join(allowed_extensions)}")

	logging.info(f"Upload request: {file.filename} (Type: {file_extension})")
	
	# Handle ZIP files by extracting and uploading each file separately
	if file_extension == '.zip':
		logging.info(f"Archive detected: {file.filename}. Extracting and processing contents...")
		import zipfile
		import tempfile
		
		temp_zip_path = f"temp_{file.filename}"
		extracted_files = []
		failed_files = []
		
		try:
			# Save uploaded ZIP temporarily
			with open(temp_zip_path, "wb") as buffer:
				shutil.copyfileobj(file.file, buffer)
			
			# Extract and process each file with unicode support
			with tempfile.TemporaryDirectory() as temp_extract_dir:
				with zipfile.ZipFile(temp_zip_path, 'r') as zip_ref:
					logging.info(f"Archive extracted: {len(zip_ref.filelist)} total files (UTF-8 filename support enabled)")
					
					# Extract files and fix filenames if needed
					for member in zip_ref.filelist:
						try:
							# Access raw filename to properly decode
							raw_filename = member.filename
							filename_to_use = raw_filename
							
							# Check if filename appears to be mojibake (UTF-8 decoded as CP437)
							if isinstance(raw_filename, str) and any(ord(c) > 127 for c in raw_filename):
								# Contains non-ASCII characters
								try:
									# First try: latin-1→utf-8
									attempt1 = raw_filename.encode('latin-1').decode('utf-8')
									filename_to_use = attempt1
									logging.debug(f"Successfully decoded via latin-1→utf-8: {raw_filename} -> {attempt1}")
								except (UnicodeDecodeError, UnicodeEncodeError):
									# If that fails, try CP437→UTF-8
									try:
										attempt2 = raw_filename.encode('cp437').decode('utf-8')
										filename_to_use = attempt2
										logging.debug(f"Successfully decoded via cp437→utf-8: {raw_filename} -> {attempt2}")
									except (UnicodeDecodeError, UnicodeEncodeError):
										# Keep original if both attempts fail
										logging.debug(f"Could not decode {raw_filename}, keeping original")
										filename_to_use = raw_filename
							
							# Now extract with the corrected filename
							member.filename = filename_to_use
							extracted_path = zip_ref.extract(member, temp_extract_dir)
							
							# Extract with corrected filename
							extracted_path = zip_ref.extract(member, temp_extract_dir)
							
						except Exception as e:
							logging.warning(f"Could not extract {member.filename}: {str(e)}")
							try:
								zip_ref.extract(member, temp_extract_dir)
							except Exception as e2:
								logging.error(f"Failed to extract {member.filename}: {str(e2)}")
				
				# Process supported files from archive
				allowed_archive_extensions = ['.pdf', '.docx', '.doc', '.html', '.txt', '.md']
				
				for root, dirs, files in os.walk(temp_extract_dir):
					for extracted_filename in files:
						extracted_file_path = os.path.join(root, extracted_filename)
						extracted_ext = os.path.splitext(extracted_filename)[1].lower()
						
						# Only process supported file types
						if extracted_ext not in allowed_archive_extensions:
							logging.info(f"Skipping unsupported file: {extracted_filename}")
							continue
						
						try:
							logging.info(f"Processing extracted file: {extracted_filename}")
							
							# Save each extracted file to database (with unicode support)
							file_id = insert_document_record(extracted_filename)
							
							# Index to Chroma
							temp_index_path = f"temp_{extracted_filename}"
							with open(temp_index_path, "wb") as buffer:
								with open(extracted_file_path, "rb") as src:
									shutil.copyfileobj(src, buffer)
							
							if index_document_to_chroma(temp_index_path, file_id):
								logging.info(f"✓ Processed {extracted_filename} (file_id: {file_id})")
								extracted_files.append({
									"filename": extracted_filename,
									"file_id": file_id
								})
							else:
								logging.error(f"Failed to index {extracted_filename}")
								delete_document_record(file_id)
								failed_files.append(extracted_filename)
							
							if os.path.exists(temp_index_path):
								os.remove(temp_index_path)
						
						except Exception as e:
							logging.error(f"Error processing {extracted_filename}: {str(e)}")
							failed_files.append(extracted_filename)
				
			logging.info(f"Archive processing complete: {len(extracted_files)} files processed, {len(failed_files)} failed")
			
			return {
				"message": f"Archive {file.filename} processed: {len(extracted_files)} files uploaded and indexed.",
				"archive_name": file.filename,
				"files_processed": len(extracted_files),
				"files_failed": len(failed_files),
				"extracted_files": extracted_files
			}
		
		except zipfile.BadZipFile as e:
			logging.error(f"Invalid ZIP file: {str(e)}")
			raise HTTPException(status_code=400, detail=f"Invalid ZIP file: {str(e)}")
		except Exception as e:
			logging.error(f"Error processing archive: {str(e)}")
			raise HTTPException(status_code=400, detail=f"Error processing archive: {str(e)}")
		finally:
			if os.path.exists(temp_zip_path):
				os.remove(temp_zip_path)
	
	else:
		# Handle regular (non-ZIP) files
		temp_file_path = f"temp_{file.filename}"

		try:
			with open(temp_file_path, "wb") as buffer:
				shutil.copyfileobj(file.file, buffer)

			file_id = insert_document_record(file.filename)
			logging.info(f"File saved to database: {file.filename} (file_id: {file_id})")
			
			success = index_document_to_chroma(temp_file_path, file_id)

			if success:
				logging.info(f"✓ Upload completed: {file.filename} (file_id: {file_id})")
				return {
					"message": f"File {file.filename} has been successfully uploaded and indexed.",
					"file_id": file_id
				}
			else:
				delete_document_record(file_id)
				logging.error(f"Failed to index {file.filename}")
				raise HTTPException(status_code=500, detail=f"Failed to index {file.filename}.")
		finally:
			if os.path.exists(temp_file_path):
				os.remove(temp_file_path)

@app.get("/list-docs", response_model=list[DocumentInfo])
def list_documents():
	return get_all_documents()

@app.post("/delete-doc")
def delete_document(request: DeleteFileRequest):
	chroma_delete_success = delete_doc_from_chroma(request.file_id)

	if chroma_delete_success:
		db_delete_success = delete_document_record(request.file_id)
		if db_delete_success:
			return {"message": f"Successfully deleted document with file_id {request.file_id} from the system."}
		else:
			return {"error": f"Deleted from Chroma but failed to delete document with file_id {request.file_id} from the database."}
	else:
		return {"error": f"Failed to delete document with file_id {request.file_id} from Chroma."}
