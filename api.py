from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn

app = FastAPI(title="NIKA API")

last_request: Optional[str] = None

class RequestModel(BaseModel):
    text: str

@app.get("/request/simple")
async def receive_request(request: RequestModel):
    """
    Receive a text request to be processed by the NIKA
    """
    last_request
    try:
        last_request = request.text
        return {"status": "success", "message": "Request received", "request": last_request}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/request/complex")
async def receive_complex_request(request: RequestModel):
    """
    Receive a complex request to be processed both by the NIKA and the LLM
    """
    last_request
    try:
        last_request = request.text
        return {"status": "success", "message": "Request received", "request": last_request}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)