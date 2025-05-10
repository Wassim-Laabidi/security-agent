from typing import Dict, Any, List, Tuple, TypedDict, Annotated, Union, Literal, Optional
from datetime import datetime
import json

from langgraph.graph import StateGraph, END
from langchain.globals import set_llm_cache
from langchain_community.cache import InMemoryCache
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
    max_steps: Optional[int]  # Added max_steps to the state

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

def analyze_history_for_services(history):
    """
    Analyze command history to find open ports and service versions
    """
    services = []

    for entry in history:
        cmd = entry.get("command", "")
        output = entry.get("output", "")

        if "nmap" in cmd and "-sV" in cmd:
            # Very simple parsing of nmap -sV output
            lines = output.splitlines()
            for line in lines:
                if "/tcp" in line or "/udp" in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        port_info = parts[0]
                        service_info = " ".join(parts[2:])
                        services.append({
                            "port": port_info,
                            "service": service_info
                        })

    return services
    
def extract_vulnerabilities(state: AttackState) -> AttackState:
    """Extract vulnerabilities from attack history"""
    # Analyze history to find open ports and services
    found_services = analyze_history_for_services(state["history"])
    
    # Update vulnerabilities
    state["vulnerabilities"] = found_services
    
    # Mark goal as reached
    state["goal_reached"] = True
    
    return state

def should_continue(state: AttackState) -> Union[Literal["continue"], Literal["finish"]]:
    # Use the max_steps from state if provided, otherwise fall back to the constant
    effective_max_steps = state.get("max_steps") or MAX_ATTACK_STEPS
    
    print(f"[DEBUG] Step Count: {state['step_count']}, Goal Reached: {state['goal_reached']}, Max Steps: {effective_max_steps}")
    
    if state["goal_reached"]:
        print("[DEBUG] Goal reached, finishing.")
        return "finish"
    if state["step_count"] >= effective_max_steps:
        print(f"[DEBUG] Max steps ({effective_max_steps}) reached, finishing.")
        return "finish"
    if state["error"] and "SSH" in state["error"]:
        print("[DEBUG] SSH error, finishing.")
        return "finish"
    print("[DEBUG] Continuing...")
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

# Make sure AttackState type is compatible with your graph definition
def run_attack_workflow(
    goal: str,
    context_manager: Optional[ContextManager] = None,
    verbose: bool = False,
    max_steps: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run the attack workflow with the specified goal
    
    Args:
        goal: The attack goal
        context_manager: Optional ContextManager instance to use
        verbose: Whether to enable verbose output
        max_steps: Maximum number of steps to execute
        
    Returns:
        Dictionary with attack results
    """
    # Set caching early
    set_llm_cache(InMemoryCache())

    # Create or use provided context manager
    internal_context = context_manager is None
    if internal_context:
        context_manager = ContextManager()
    context_manager.set_attack_goal(goal)

    # Log if max_steps is specified
    if max_steps is not None:
        print(f"[INFO] Using custom max_steps: {max_steps} instead of default: {MAX_ATTACK_STEPS}")

    # Create and compile the workflow
    workflow = create_attack_workflow()
    app = workflow.compile()

    # Define initial state directly as dict
    initial_state = {
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
        "error": "",
        "max_steps": max_steps  # Add max_steps to the initial state
    }

    # Execute the workflow
    result = app.invoke(
        initial_state,
        config={"recursion_limit": 200}
    )

    # If we created the context manager internally, save final state
    if internal_context:
        for step in result.get("history", []):
            context_manager.add_attack_step(step)
        for vuln in result.get("vulnerabilities", []):
            context_manager.add_vulnerability(vuln)

    # Return summary
    return {
        "goal": result.get("goal"),
        "goal_reached": result.get("goal_reached", False),
        "steps_executed": result.get("step_count", 0),
        "vulnerabilities": result.get("vulnerabilities", []),
        "history": result.get("history", []),
        "error": result.get("error", "")
    }