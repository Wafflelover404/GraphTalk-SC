from fastapi import FastAPI, HTTPException, Query, UploadFile, File, Request, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Union
import uvicorn
import logging
import os
import zipfile
import shutil
import uuid
import glob
from fastapi.concurrency import run_in_threadpool
import secrets
import toml
import bcrypt  # New import for bcrypt hashing

from nika_search import kb_search
from llm import llm_call
from memloader import load_scs_directory

app = FastAPI(title="NIKA API")
path_to_kb = "./unpacked_kbs"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UPLOAD_DIR = "uploaded_kbs"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Path to the secrets file
SECRETS_PATH = os.path.expanduser("~/secrets.toml")

class RequestModel(BaseModel):
    text: str

class ResponseModel(BaseModel):
    status: str
    message: str
    response: Union[List[str], str, dict]

@app.middleware("http")
async def check_token(request: Request, call_next):
    # Skip token check for the create_token endpoint
    if request.url.path == "/create_token":
        response = await call_next(request)
        return response
    
    # Check if token exists
    if not os.path.exists(SECRETS_PATH):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Token was not yet created. Send a POST request to '/create_token' to create a token."}
        )
    
    # Read the expected token hash
    with open(SECRETS_PATH, "r") as f:
        secrets_data = toml.load(f)
    stored_hash = secrets_data.get("access_token_hash")
    
    if not stored_hash:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Token file exists but is invalid."}
        )
    
    # Check Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Missing Authorization header"}
        )
    
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            raise ValueError("Invalid authentication scheme")
    except ValueError:
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid Authorization header format"}
        )
    
    # Verify token against stored hash
    try:
        if not bcrypt.checkpw(token.encode('utf-8'), stored_hash.encode('utf-8')):
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": "Invalid token"}
            )
    except Exception as e:
        logger.error(f"Token verification error: {str(e)}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Token verification failed"}
        )
    
    # Proceed if token is valid
    response = await call_next(request)
    return response

@app.post("/create_token")
async def create_token():
    """Generate a new access token and save its bcrypt hash to ~/secrets.toml"""
    token = secrets.token_hex(32)
    token_bytes = token.encode('utf-8')
    
    # Generate bcrypt hash with secure settings
    salt = bcrypt.gensalt(rounds=12)  # 12 is a good balance between security and performance
    hashed_token = bcrypt.hashpw(token_bytes, salt)
    
    # Save hash to file
    os.makedirs(os.path.dirname(SECRETS_PATH), exist_ok=True)
    with open(SECRETS_PATH, "w") as f:
        toml.dump({"access_token_hash": hashed_token.decode('utf-8')}, f)
    
    return {"token": token}  # Return plain token (only shown once)

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
            },
            "/create_token": {
                "method": "POST",
                "description": "Generates a new access token required for authentication."
            }
        }
    }

@app.post("/query", response_model=ResponseModel)
async def query_endpoint(request: RequestModel, humanize: bool = Query(False, description="If true, use LLM to humanize the response")):
    logger.info(f"Received request: {request.text} | humanize={humanize}")

    try:
        kb_results = kb_search(request.text)
        if isinstance(kb_results, list):
            kb_results = list(dict.fromkeys(kb_results))
        if not isinstance(kb_results, (list, str, dict)):
            kb_results = str(kb_results)
        if humanize:
            context = "\n".join(kb_results) if isinstance(kb_results, list) else str(kb_results)
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
    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only zip files are allowed.")
    
    save_path = os.path.join(UPLOAD_DIR, file.filename)
    unpacked_root = os.path.abspath("unpacked_kbs")
    os.makedirs(unpacked_root, exist_ok=True)
    
    unique_dir = os.path.join(unpacked_root, f"{os.path.splitext(file.filename)[0]}_{uuid.uuid4().hex}")
    os.makedirs(unique_dir, exist_ok=True)
    logger.info(f"Unique extraction directory: {unique_dir}")
    
    try:
        with open(save_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                buffer.write(chunk)
        
        with zipfile.ZipFile(save_path, 'r') as zip_ref:
            zip_ref.extractall(unique_dir)
            logger.info(f"Succesfully extracted {save_path} to {unique_dir}")
        
        load_status = await run_in_threadpool(load_scs_directory, unique_dir)
        logger.info(f"SCS files loaded with status: {load_status}")
        
        return {
            "status": "success",
            "message": f"File saved as {save_path}",
            "unique_dir": unique_dir,
            "load_status": load_status
        }
    
    except Exception as e:
        logger.error(f"Error during file processing: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
    
    finally:
        if os.path.exists(unique_dir):
            try:
                shutil.rmtree(unique_dir)
                logger.info(f"Cleaned up directory {unique_dir}")
            except Exception as cleanup_err:
                logger.warning(f"Failed to clean up directory {unique_dir}: {cleanup_err}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=9001)