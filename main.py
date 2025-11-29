import os
import json
import uuid
import logging
from datetime import datetime
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import asyncio

from config import QUIZ_SECRET
from solver import QuizSolver

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Analysis Quiz Solver")

class SolveRequest(BaseModel):
    email: str
    secret: str
    url: str

@app.post("/solve")
async def solve(request: SolveRequest, background_tasks: BackgroundTasks):
    """Endpoint to submit a quiz task for solving."""
    request_id = str(uuid.uuid4())
    
    # Validate required fields
    if not request.email or not request.secret or not request.url:
        logger.warning(f"[{request_id}] Missing required fields")
        raise HTTPException(status_code=400, detail="Missing required fields: email, secret, url")
    
    # Verify secret
    if request.secret != QUIZ_SECRET:
        logger.warning(f"[{request_id}] Invalid secret provided")
        raise HTTPException(status_code=403, detail="Invalid secret")
    
    # Validate URL format
    if not request.url.startswith("http://") and not request.url.startswith("https://"):
        logger.warning(f"[{request_id}] Invalid URL scheme")
        raise HTTPException(status_code=400, detail="URL must be http or https")
    
    logger.info(f"[{request_id}] Valid request accepted. Email: {request.email}, URL: {request.url}")
    
    # Start solver in background
    background_tasks.add_task(
        _run_solver,
        request_id=request_id,
        email=request.email,
        url=request.url,
        secret=request.secret
    )
    
    return JSONResponse(status_code=200, content={"status": "accepted", "request_id": str(request_id)})

async def _run_solver(request_id: str, email: str, url: str, secret: str):
    """Run the solver in background with 3-minute timeout."""
    start_time = datetime.now()
    timeout_seconds = 180  # 3 minutes
    
    logger.info(f"[{request_id}] Starting solve for {email} at {url}")
    
    try:
        solver = QuizSolver(
            request_id=request_id,
            email=email,
            secret=secret,
            start_time=start_time,
            timeout_seconds=timeout_seconds
        )
        result = await asyncio.wait_for(
            solver.solve(url),
            timeout=timeout_seconds + 5
        )
        logger.info(f"[{request_id}] Solver completed: {result}")
    except asyncio.TimeoutError:
        logger.warning(f"[{request_id}] Solver exceeded 3-minute timeout")
    except Exception as e:
        logger.error(f"[{request_id}] Solver error: {type(e).__name__}: {e}", exc_info=True)

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)