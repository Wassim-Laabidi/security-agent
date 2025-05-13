from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import FileResponse, Response
import subprocess
import json
import os
import tempfile
import datetime
from typing import Optional
import io
import markdown
import pdfkit  # You'll need to install this: pip install pdfkit (requires wkhtmltopdf)
import sys


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
    
    # Save start time
    start_time = datetime.datetime.now()
    
    # Build command - use the main.py implementation with --goal parameter
    cmd = ["python", os.path.join(os.path.dirname(__file__), "main.py"), "--goal", goal]
    if verbose:
        cmd.append("--verbose")
    if max_steps:
        cmd.extend(["--max-steps", str(max_steps)])
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Calculate elapsed time
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        response_data = {
            "success": result.returncode == 0, 
            "output": result.stdout, 
            "error": result.stderr,
            "elapsed_time": elapsed_time,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        # Save report
        report_id = f"goal_test_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        results_dir = os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(results_dir, exist_ok=True)
        
        report_data = {
            "type": "Goal-Based Test",
            "name": goal,
            "date": start_time.strftime("%Y-%m-%d"),
            "time": start_time.strftime("%H:%M:%S"),
            "elapsed_time": elapsed_time,
            "result": response_data
        }
        
        with open(os.path.join(results_dir, report_id), "w") as f:
            json.dump(report_data, f, indent=2)
            
        return response_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error running test: {str(e)}")

@app.get("/attack-goals")
async def get_attack_goals(token: str = Depends(get_current_user)):
    """Get the list of predefined attack goals from main.py's settings"""
    try:
        # Import the default attack goals from the settings module
        sys.path.append(os.path.dirname(__file__))
        from config.settings import DEFAULT_ATTACK_GOALS
        return {"goals": DEFAULT_ATTACK_GOALS}
    except ImportError:
        # Fallback in case the import fails
        return {"goals": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching attack goals: {str(e)}")

@app.post("/run-task")
async def run_task_test(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...), 
    task_id: str = "", 
    verbose: bool = False, 
    token: str = Depends(get_current_user)
):
    # Save start time
    start_time = datetime.datetime.now()
    
    # Create temporary file with safe handling
    temp_fd, temp_path = tempfile.mkstemp(suffix='.json')
    try:
        with os.fdopen(temp_fd, 'wb') as f:
            # Process the file in chunks to handle large files
            chunk_size = 1024 * 1024  # 1MB chunks
            while content := file.file.read(chunk_size):
                f.write(content)
        
        # Build command - use main.py with --config parameter
        cmd = ["python", os.path.join(os.path.dirname(__file__), "main.py"), "--config", temp_path]
        if task_id:
            cmd.extend(["--task", task_id])
        else:
            cmd.append("--run-all")
        if verbose:
            cmd.append("--verbose")
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        # Calculate elapsed time
        end_time = datetime.datetime.now()
        elapsed_time = (end_time - start_time).total_seconds()
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_temp_file, temp_path)
        
        # Generate response
        response_data = {
            "success": result.returncode == 0, 
            "output": result.stdout, 
            "error": result.stderr,
            "elapsed_time": elapsed_time,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat()
        }
        
        # Save report
        report_id = f"task_test_{start_time.strftime('%Y%m%d_%H%M%S')}.json"
        results_dir = os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(results_dir, exist_ok=True)
        
        # Try to get task name from config file
        task_name = task_id if task_id else "All Tasks"
        try:
            with open(temp_path, 'r') as f:
                config_data = json.load(f)
                if task_id:
                    for task in config_data.get("tasks", []):
                        if task.get("id") == task_id:
                            task_name = task.get("name", task_id)
                            break
        except:
            pass  # If we can't parse the config file, just use the task_id
        
        report_data = {
            "type": "Task-Based Test",
            "name": task_name,
            "date": start_time.strftime("%Y-%m-%d"),
            "time": start_time.strftime("%H:%M:%S"),
            "elapsed_time": elapsed_time,
            "result": response_data
        }
        
        with open(os.path.join(results_dir, report_id), "w") as f:
            json.dump(report_data, f, indent=2)
            
        return response_data
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
        
    reports = []
    for f in os.listdir(results_dir):
        if f.endswith(".json"):
            file_path = os.path.join(results_dir, f)
            try:
                with open(file_path, 'r') as report_file:
                    report_data = json.load(report_file)
                    report_info = {
                        "id": f,
                        "name": report_data.get("name", f),
                        "type": report_data.get("type", "Unknown"),
                        "date": report_data.get("date", ""),
                        "time": report_data.get("time", ""),
                        "timestamp": os.path.getmtime(file_path)
                    }
                    reports.append(report_info)
            except:
                # Fall back to basic info if JSON parsing fails
                reports.append({
                    "id": f,
                    "name": f,
                    "type": "Unknown",
                    "timestamp": os.path.getmtime(file_path)
                })
    
    # Sort by timestamp descending
    reports.sort(key=lambda x: x["timestamp"], reverse=True)
    return {"reports": reports}

def generate_pdf_from_report(report_data):
    """Generate a PDF from the report data"""
    # Create markdown content
    md_content = f"""
# Security Test Report
- **Test Type:** {report_data.get('type', 'Unknown')}
- **Test Name:** {report_data.get('name', 'Unknown')}
- **Date:** {report_data.get('date', '')}
- **Time:** {report_data.get('time', '')}
- **Time Elapsed:** {report_data.get('elapsed_time', 0):.2f} seconds

## Test Output
```
{report_data.get('result', {}).get('output', 'No output available')}
```

## Summary
**Status:** {'Successful' if report_data.get('result', {}).get('success', False) else 'Failed'}

## Errors (if any)
```
{report_data.get('result', {}).get('error', 'No errors')}
```
"""
    
    # Convert markdown to HTML
    html_content = markdown.markdown(md_content)
    
    # Wrap in proper HTML document
    html_doc = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Security Test Report</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 40px; }}
            h1 {{ color: #2c3e50; }}
            h2 {{ color: #3498db; margin-top: 30px; }}
            pre {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; }}
            .info-item {{ margin-bottom: 10px; }}
            .success {{ color: green; }}
            .failed {{ color: red; }}
        </style>
    </head>
    <body>
        {html_content}
    </body>
    </html>
    """
    
    # Convert HTML to PDF using pdfkit
    try:
        pdf_content = pdfkit.from_string(html_doc, False)
        return pdf_content
    except Exception as e:
        # If PDF generation fails, fallback to HTML
        return html_doc.encode('utf-8')

@app.get("/report/{report_id}/pdf")
async def get_report_pdf(report_id: str, token: str = Depends(get_current_user)):
    report_path = os.path.join(os.path.dirname(__file__), "results", report_id)
    if not os.path.exists(report_path):
        raise HTTPException(status_code=404, detail="Report not found")
    
    try:
        # Load the report data
        with open(report_path, 'r') as f:
            report_data = json.load(f)
        
        # Generate PDF from report data
        pdf_content = generate_pdf_from_report(report_data)
        
        # Check if we got PDF or HTML (fallback)
        content_type = "application/pdf"
        file_extension = "pdf"
        
        # If the content starts with <!DOCTYPE html>, it's HTML
        if pdf_content.startswith(b"<!DOCTYPE html>") or pdf_content.startswith(b"<html"):
            content_type = "text/html"
            file_extension = "html"
        
        # Return the response
        return Response(
            content=pdf_content,
            media_type=content_type,
            headers={"Content-Disposition": f"attachment; filename=report_{report_id}.{file_extension}"}
        )
    except Exception as e:
        # Fallback to just returning the JSON file if PDF generation fails
        return FileResponse(
            path=report_path,
            media_type="application/json",
            filename=f"report_{report_id}.json"
        )

# Add this import at the top of the file
