import streamlit as st
import requests
import json
import time
from pathlib import Path

# FastAPI backend URL
BACKEND_URL = "http://localhost:8000"

# Predefined testing goals
PREDEFINED_GOALS = [
    "Scan the local network interfaces and identify all open TCP ports on the system",
    "Enumerate all user accounts",
    "Find and exploit a SQL injection vulnerability",
    "Attempt privilege escalation",
]

def login():
    """Handle user authentication"""
    st.title("Security Testing Agent - Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        response = requests.post(f"{BACKEND_URL}/login", json={"username": username, "password": password})
        if response.status_code == 200:
            st.session_state["token"] = response.json()["access_token"]
            st.success("Logged in successfully!")
            st.rerun()
        else:
            st.error("Invalid credentials")

def run_goal_based_test(goal, verbose, max_steps):
    """Run a goal-based test via the FastAPI backend"""
    payload = {
        "goal": goal,
        "verbose": verbose,
        "max_steps": max_steps
    }
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    response = requests.post(f"{BACKEND_URL}/run-goal", json=payload, headers=headers)
    return response.json()

def run_task_based_test(config_file, task_id, verbose):
    """Run a task-based test via the FastAPI backend"""
    files = {"file": config_file}
    payload = {"task_id": task_id, "verbose": verbose}
    headers = {"Authorization": f"Bearer {st.session_state['token']}"}
    response = requests.post(f"{BACKEND_URL}/run-task", files=files, data=payload, headers=headers)
    return response.json()

def main_dashboard():
    """Main dashboard with tabs for goal-based and task-based testing"""
    st.title("Security Testing Agent Dashboard")
    
    # Tabs for different testing modes
    tab1, tab2, tab3 = st.tabs(["Goal-Based Testing", "Task-Based Testing", "Reports"])

    # Goal-Based Testing Tab
    with tab1:
        st.header("Goal-Based Testing")
        goal = st.text_input("Enter security testing goal", value="")
        predefined_goal = st.selectbox("Or select a predefined goal", ["Custom"] + PREDEFINED_GOALS)
        if predefined_goal != "Custom":
            goal = predefined_goal
        verbose = st.checkbox("Verbose Output", value=False)
        max_steps = st.number_input("Max Steps (optional)", min_value=1, value=15, step=1)
        if st.button("Run Goal-Based Test"):
            if goal:
                with st.spinner("Running security test..."):
                    result = run_goal_based_test(goal, verbose, max_steps)
                    st.session_state["result"] = result
                    st.success("Test completed!")
            else:
                st.error("Please enter or select a goal")

    # Task-Based Testing Tab
    with tab2:
        st.header("Task-Based Testing")
        config_file = st.file_uploader("Upload attack_tasks.json", type=["json"])
        if config_file:
            config_data = json.load(config_file)
            task_ids = [task["id"] for task in config_data.get("tasks", [])] + ["Run All"]
            task_id = st.selectbox("Select Task ID (or Run All)", task_ids)
            verbose = st.checkbox("Verbose Output (Task)", value=False)
            if st.button("Run Task-Based Test"):
                with st.spinner("Running task-based test..."):
                    result = run_task_based_test(config_file, task_id if task_id != "Run All" else "", verbose)
                    st.session_state["result"] = result
                    st.success("Test completed!")
        else:
            st.warning("Please upload a configuration file")

    # Reports Tab
    with tab3:
        st.header("Test Reports")
        headers = {"Authorization": f"Bearer {st.session_state['token']}"}
        response = requests.get(f"{BACKEND_URL}/reports", headers=headers)
        reports = response.json().get("reports", [])
        if reports:
            st.table(reports)
            report_id = st.selectbox("Select Report to Download", [r["id"] for r in reports])
            if st.button("Download PDF Report"):
                response = requests.get(f"{BACKEND_URL}/report/{report_id}/pdf", headers=headers)
                st.download_button(
                    label="Download PDF",
                    data=response.content,
                    file_name=f"report_{report_id}.pdf",
                    mime="application/pdf"
                )
        else:
            st.info("No reports available")

    # Real-Time Output Panel
    if "result" in st.session_state:
        st.header("Test Results")
        with st.expander("View Detailed Results"):
            st.json(st.session_state["result"])

def main():
    """Main entry point for the Streamlit app"""
    if "token" not in st.session_state:
        login()
    else:
        main_dashboard()

if __name__ == "__main__":
    main()