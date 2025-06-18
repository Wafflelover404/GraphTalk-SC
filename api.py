from fastapi import FastAPI, HTTPException, Query, UploadFile, File
from pydantic import BaseModel
from typing import Optional, List, Union
import uvicorn
import logging
import os
import zipfile

from nika_search import kb_search
from llm import llm_call

app = FastAPI(title="NIKA API")
path_to_kb = "/Users/ivanafanasyeff/Documents/technopark/nika/knowledge-base"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploaded_kbs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

class RequestModel(BaseModel):
    text: str

class ResponseModel(BaseModel):
    status: str
    message: str
    response: Union[List[str], str, dict]

@app.get("/")
async def landing_page():
    return {
        "description": "NIKA API provides functionalities for querying a knowledge base and uploading knowledge base files.",
        "endpoints": {
            "/query": {
                "method": "POST",
                "description": "Processes a text query against the knowledge base. Optionally, the response can be humanized using a language model.",
                "parameters": {
                    "text": "The query text to search in the knowledge base.",
                    "humanize": "Optional boolean to indicate if the response should be humanized."
                },
                "response": "Returns the search results or a humanized response."
            },
            "/upload/kb_zip": {
                "method": "POST",
                "description": "Uploads a zip file containing knowledge base data and extracts it to the server.",
                "parameters": {
                    "file": "The zip file to upload."
                },
                "response": "Returns the status of the upload operation."
            }
        }
    }

@app.post("/query", response_model=ResponseModel)
async def query_endpoint(request: RequestModel, humanize: bool = Query(False, description="If true, use LLM to humanize the response")):
    """Process requests using KB search, optionally humanized by LLM"""
    logger.info(f"Received request: {request.text} | humanize={humanize}")

    try:
        kb_results = kb_search(request.text)
        if isinstance(kb_results, list):
            kb_results = list(dict.fromkeys(kb_results))
        if not isinstance(kb_results, (list, str, dict)):
            kb_results = str(kb_results)
        if humanize:
            if isinstance(kb_results, list):
                context = "\n".join(kb_results)
            else:
                context = str(kb_results)
            llm_response = llm_call(request.text, context)
            return {
                "status": "success",
                "message": "Request processed with LLM humanization",
                "response": llm_response
            }
        else:
            return {
                "status": "success",
                "message": "Request processed",
                "response": kb_results
            }
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/upload/kb_zip")
async def upload_kb_zip(file: UploadFile = File(...)):
    """
    Accept a zip file and save it to the local uploaded_kbs directory.
    Input:
        Path to file
    """
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only zip files are allowed.")
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    try:
        with open(save_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024): 
                buffer.write(chunk)
            with zipfile.ZipFile(save_path, 'r') as zip_ref:
                zip_ref.extractall(path_to_kb)
                print(f"Succesfully written file {save_path} to {path_to_kb}")
        return {"status": "success", "message": f"File saved as {save_path}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)