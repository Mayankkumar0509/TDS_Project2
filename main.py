import logging
import json
import uuid
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from pydantic import BaseModel
import asyncio

from config import QUIZ_SECRET, LOG_LEVEL, LOGS_DIR
from solver import QuizSolver

# Setup logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'solver.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(title="LLM Quiz Solver API", version="1.0.0")

class SolveRequest(BaseModel):
    email: str
    secret: str
    url: str

class ErrorResponse(BaseModel):
    error: str
    status_code: int

class SuccessResponse(BaseModel):
    status: str
    task_id: str

# In-memory task tracking (in production, use database)
active_tasks = {}

@app.post("/solve", response_model=SuccessResponse)
async def solve(request: SolveRequest, background_tasks: BackgroundTasks):
    """
    Receive a quiz task, verify secret, and start async solver.
    
    Returns HTTP 200 immediately with task_id.
    Solver runs in background with 3-minute timeout.
    """
    # Validate request
    if not request.email or not request.secret or not request.url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required fields: email, secret, url"
        )
    
    # Verify secret
    if request.secret != QUIZ_SECRET:
        logger.warning(f"Invalid secret provided for {request.email}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret"
        )
    
    # Generate task ID
    task_id = str(uuid.uuid4())
    
    # Schedule solver in background
    background_tasks.add_task(_run_solver, task_id, request.email, request.url, request.secret)
    
    logger.info(f"Task {task_id} scheduled for {request.email} at {request.url}")
    
    return {
        "status": "accepted",
        "task_id": task_id
    }

async def _run_solver(task_id: str, email: str, url: str, secret: str):
    """Background task to run solver."""
    solver = QuizSolver(task_id)
    result = await solver.solve(email, url, secret)
    active_tasks[task_id] = result

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok"}

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a background task."""
    if task_id in active_tasks:
        return {"task_id": task_id, "result": active_tasks[task_id]}
    else:
        return {"task_id": task_id, "status": "running or not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)