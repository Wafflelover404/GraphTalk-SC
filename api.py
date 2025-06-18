from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Union
import uvicorn
import logging

from nika_search import kb_search
from llm import llm_call

app = FastAPI(title="NIKA API")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RequestModel(BaseModel):
    text: str

class ResponseModel(BaseModel):
    status: str
    message: str
    response: Union[List[str], str, dict]

@app.post("/resp/simple", response_model=ResponseModel)
async def receive_request(request: RequestModel):
    """Process simple text requests using KB search"""
    logger.info(f"Received simple request: {request.text}")

    try:
        results = kb_search(request.text)
        if not isinstance(results, (list, str, dict)):
            results = str(results)
        return {"status": "success", "message": "Request processed", "response": results}
    except Exception as e:
        logger.error(f"Error processing simple request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.post("/resp/complex", response_model=ResponseModel)
async def receive_complex_request(request: RequestModel):
    """Process complex requests using KB search + LLM"""
    logger.info(f"Received complex request: {request.text}")

    try:
        kb_results = kb_search(request.text)
        
        if isinstance(kb_results, list):
            context = "\n".join(kb_results)
        else:
            context = str(kb_results)
        
        llm_response = llm_call(request, context)
        return {
            "status": "success",
            "message": "Complex request processed",
            "response": llm_response
        }
    except Exception as e:
        logger.error(f"Error processing complex request: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)