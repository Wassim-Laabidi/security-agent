from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse
import subprocess
import json
import os
import tempfile
from typing import Optional

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Dummy authentication (replace with proper auth)
async def get_current_user(token: str = Depends(oauth2_scheme)):
    if token != "valid-token":  # Replace with actual token validation
        raise HTTPException(status_code=401, detail="Invalid token")
    return token

@app.post("/login")
async def login(credentials: dict):
    # Dummy authentication logic - REPLACE WITH PROPER AUTH
    if credentials.get("username") == "admin" and credentials.get("password") == "password":
        return {"access_token": "valid-token", "token_type": "bearer"}
    raise HTTPException(status_code=401, detail="Invalid credentials")

def cleanup_temp_file(file_path: str):
    """Remove temporary file"""
    if os.path.exists(file_path):
        os.remove(file_path)

@app.post("/run-goal")
async def run_goal_test(payload: dict, token: str = Depends(get_current_user)):
    goal = payload.get("goal")
    if not goal:
        raise HTTPException(status_code=400, detail="Goal is required")
        
    verbose = payload.get("verbose", False)
    max_steps = payload.get("max_steps")
    
    # Build command
    cmd = ["python", os.path.join(os.path.dirname(__file__), "main.py"), "--goal", goal]
    if verbose:
        cmd.append("--verbose")
    if max_steps:
        cmd.extend(["--max-steps", str(max_steps)])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            return {"success": False, "output": result.stdout, "error": result.stderr}
        return {"success": True, "output": result.stdout, "error": result.stderr}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running test: {str(e)}")

@app.post("/run-task")
async def run_task_test(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    task_id: str = "", 
    verbose: bool = False, 
    token: str = Depends(get_current_user)
):
    # Create temporary file with safe handling
    temp_fd, temp_path = tempfile.mkstemp(suffix='.json')
    try:
        with os.fdopen(temp_fd, 'wb') as f:
            # Process the file in chunks to handle large files
            chunk_size = 1024 * 1024  # 1MB chunks
            while content := file.file.read(chunk_size):
                f.write(content)
        
        # Build command
        cmd = ["python", os.path.join(os.path.dirname(__file__), "main.py"), "--config", temp_path]
        if task_id:
            cmd.extend(["--task", task_id])
        else:
            cmd.append("--run-all")
        if verbose:
            cmd.append("--verbose")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_temp_file, temp_path)
        
        if result.returncode != 0:
            return {"success": False, "output": result.stdout, "error": result.stderr}
        return {"success": True, "output": result.stdout, "error": result.stderr}
    except Exception as e:
        # Make sure we cleanup on exception
        background_tasks.add_task(cleanup_temp_file, temp_path)
        raise HTTPException(status_code=500, detail=f"Error running test: {str(e)}")

@app.get("/reports")
async def list_reports(token: str = Depends(get_current_user)):
    # List reports from results directory
    results_dir = os.path.join(os.path.dirname(__file__), "results")
    if not os.path.exists(results_dir):
        return {"reports": []}
        
    reports = [
        {"id": f, "name": f, "timestamp": os.path.getmtime(os.path.join(results_dir, f))} 
        for f in os.listdir(results_dir) 
        if f.endswith(".json")
    ]
    # Sort by timestamp descending
    reports.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"reports": reports}

@app.get("/report/{report_id}/pdf")
async def get_report_pdf(report_id: str, token: str = Depends(get_current_user)):
    # For a real implementation, you'd generate a PDF here
    # This is just a placeholder that returns the JSON file
    report_path = os.path.join(os.path.dirname(__file__), "results", report_id)
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Report not found")
    
    # In a real implementation, convert report to PDF here
    # For now, just return the JSON file
    return FileResponse(
        path=report_path,
        media_type="application/json",
        filename=f"report_{report_id}.json"
    )