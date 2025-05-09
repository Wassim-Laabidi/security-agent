from typing import Dict, Any, List, Tuple, TypedDict, Annotated, Union, Literal
from datetime import datetime
import json

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from config.settings import MAX_ATTACK_STEPS, USE_SUMMARIZER
from agents.planner import PlannerAgent
from agents.interpreter import InterpreterAgent
from agents.summarizer import SummarizerAgent
from agents.extractor import ExtractorAgent
from utils.ssh_client import SSHClient
from utils.context_manager import ContextManager


# Define the state for our workflow
class AttackState(TypedDict):
    goal: str
    context: str
    current_plan: Dict[str, Any]
    current_step: str
    step_command: str
    step_output: str
    history: List[Dict[str, Any]]
    vulnerabilities: List[Dict[str, Any]]
    step_count: int
    goal_reached: bool
    error: str

# Node implementations
def initialize_attack(state: AttackState) -> AttackState:
    """Initialize a new attack with the specified goal"""
    ssh_client = SSHClient()
    
    # Try to establish an SSH connection
    if not ssh_client.connect():
        return {**state, "error": "Failed to establish SSH connection"}
    
    # Close the connection for now - it will be reopened when needed
    ssh_client.close()
    
    # Initialize the state
    return {
        **state,
        "context": f"ATTACK GOAL: {state['goal']}\n\n",
        "current_plan": {},
        "current_step": "",
        "step_command": "",
        "step_output": "",
        "history": [],
        "vulnerabilities": [],
        "step_count": 0,
        "goal_reached": False,
        "error": ""
    }

def plan_attack(state: AttackState) -> AttackState:
    """Generate an attack plan using the planner agent"""
    planner = PlannerAgent()
    
    # Get plan based on the current context and goal
    plan = planner.invoke(state["context"], state["goal"])
    
    # Update the state with the new plan
    return {
        **state,
        "current_plan": plan,
        "current_step": plan["steps"][0] if plan.get("steps") else "",
        "goal_reached": plan.get("goal_reached", False)
    }

def interpret_step(state: AttackState) -> AttackState:
    """Convert the current step to an executable command"""
    interpreter = InterpreterAgent()
    
    # If no current step, return the state unchanged
    if not state["current_step"]:
        return {**state, "error": "No step to interpret"}
    
    # Convert the step to a command
    command = interpreter.invoke(state["context"], state["current_step"])
    
    # Update the state with the command
    return {
        **state,
        "step_command": command
    }

def execute_command(state: AttackState) -> AttackState:
    """Execute the command on the target system"""
    ssh_client = SSHClient()
    
    # If no command, return the state unchanged
    if not state["step_command"]:
        return {**state, "error": "No command to execute"}
    
    # Try to establish an SSH connection
    if not ssh_client.connect():
        return {**state, "error": "Failed to establish SSH connection"}
    
    # Execute the command
    output, error = ssh_client.execute_command(state["step_command"])
    ssh_client.close()
    
    if error:
        return {**state, "step_output": f"Error: {error}", "error": error}
    
    # Update the state with the command output
    return {
        **state,
        "step_output": output
    }

def update_history(state: AttackState) -> AttackState:
    """Update the attack history with the latest step"""
    # Create a record of the step
    step_data = {
        "command": state["step_command"],
        "output": state["step_output"],
        "plan": state["current_step"],
        "timestamp": datetime.now().isoformat()
    }
    
    # Add to history
    updated_history = state["history"] + [step_data]
    
    # Update the context with the new step
    step_context = f"--- Step {state['step_count'] + 1} ---\n"
    step_context += f"Plan: {state['current_step']}\n"
    step_context += f"Command: {state['step_command']}\n"
    step_context += f"Output: {state['step_output']}\n\n"
    
    updated_context = state["context"] + step_context
    
    # Increment step counter
    step_count = state["step_count"] + 1
    
    return {
        **state,
        "history": updated_history,
        "context": updated_context,
        "step_count": step_count
    }

def summarize_context(state: AttackState) -> AttackState:
    """Summarize the context if it's getting too large"""
    if not USE_SUMMARIZER:
        return state
    
    # Only summarize if the context is large enough
    if len(state["context"]) < 8000:
        return state
    
    summarizer = SummarizerAgent()
    summary = summarizer.invoke(state["context"])
    
    # Create a new summarized context
    summarized_context = f"ATTACK GOAL: {state['goal']}\n\n"
    summarized_context += f"ATTACK HISTORY SUMMARY:\n{summary}\n\n"
    
    if state["current_plan"].get("steps"):
        summarized_context += "CURRENT PLAN:\n"
        for i, step in enumerate(state["current_plan"]["steps"]):
            summarized_context += f"{i+1}. {step}\n"
    
    return {
        **state,
        "context": summarized_context
    }

def extract_vulnerabilities(state: AttackState) -> AttackState:
    """Extract vulnerabilities from the attack history"""
    extractor = ExtractorAgent()
    findings = extractor.invoke(state["context"])
    
    return {
        **state,
        "vulnerabilities": findings.get("vulnerabilities", [])
    }

def should_continue(state: AttackState) -> Union[Literal["continue"], Literal["finish"]]:
    """Determine if the attack should continue or finish"""
    # Stop if the goal is reached
    if state["goal_reached"]:
        return "finish"
    
    # Stop if max steps reached
    if state["step_count"] >= MAX_ATTACK_STEPS:
        return "finish"
    
    # Stop if there's a critical error
    if state["error"] and "Failed to establish SSH connection" in state["error"]:
        return "finish"
    
    # Otherwise continue
    return "continue"

def select_next_step(state: AttackState) -> AttackState:
    """Select the next step from the current plan"""
    # If there are no steps in the plan, return unchanged
    if not state["current_plan"].get("steps"):
        return {**state, "error": "No steps in the current plan"}
    
    # Get steps from the current plan
    steps = state["current_plan"]["steps"]
    
    # If we've executed the only step or all steps, get a new plan next time
    if len(steps) <= 1:
        return {**state, "current_step": ""}
    
    # Otherwise, move to the next step in the plan
    return {**state, "current_step": steps[1], "current_plan": {**state["current_plan"], "steps": steps[1:]}}

# Create the attack workflow graph
def create_attack_workflow() -> StateGraph:
    """Create the attack workflow graph using LangGraph"""
    # Initialize the workflow with the starting state
    workflow = StateGraph(AttackState)
    
    # Add all the nodes
    workflow.add_node("initialize", initialize_attack)
    workflow.add_node("plan", plan_attack)
    workflow.add_node("interpret", interpret_step)
    workflow.add_node("execute", execute_command)
    workflow.add_node("update_history", update_history)
    workflow.add_node("summarize", summarize_context)
    workflow.add_node("extract", extract_vulnerabilities)
    workflow.add_node("select_next", select_next_step)
    
    # Define the edges between nodes
    # Initial flow
    workflow.add_edge("initialize", "plan")
    workflow.add_edge("plan", "interpret")
    workflow.add_edge("interpret", "execute")
    workflow.add_edge("execute", "update_history")
    workflow.add_edge("update_history", "summarize")
    
    # Conditional branching based on the current state
    workflow.add_conditional_edges(
        "summarize",
        should_continue,
        {
            "continue": "select_next",
            "finish": "extract"
        }
    )
    
    # Cycle back or get a new plan
    workflow.add_conditional_edges(
        "select_next",
        lambda state: "plan" if not state["current_step"] else "interpret",
        {
            "plan": "plan",
            "interpret": "interpret"
        }
    )
    
    # Set the entry point
    workflow.set_entry_point("initialize")
    
    # Set the exit point
    workflow.add_edge("extract", END)
    
    return workflow

def run_attack_workflow(goal: str) -> Dict[str, Any]:
    """
    Run the attack workflow with the specified goal
    
    Args:
        goal: The attack goal
        
    Returns:
        Dictionary with attack results
    """

    # Create the workflow
    workflow = create_attack_workflow()
    
    # Compile the workflow
    app = workflow.compile()

    
    # Run the workflow with the initial state
    initial_state: AttackState = {
        "goal": goal,
        "context": "",
        "current_plan": {},
        "current_step": "",
        "step_command": "",
        "step_output": "",
        "history": [],
        "vulnerabilities": [],
        "step_count": 0,
        "goal_reached": False,
        "error": ""
    }
    
    # Execute the workflow
    result = app.invoke(initial_state)
    
    # Return the final state
    return {
        "goal": goal,
        "goal_reached": result["goal_reached"],
        "steps_executed": result["step_count"],
        "vulnerabilities": result["vulnerabilities"],
        "history": result["history"],
        "error": result["error"]
    }