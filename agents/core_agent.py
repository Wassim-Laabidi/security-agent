import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

from config.settings import USE_SUMMARIZER, MAX_ATTACK_STEPS
from utils.ssh_client import SSHClient
from utils.context_manager import ContextManager
from agents.planner import PlannerAgent
from agents.interpreter import InterpreterAgent
from agents.summarizer import SummarizerAgent
from agents.extractor import ExtractorAgent

class CoreAgent:
    """
    Core agent that orchestrates the security testing process by coordinating
    the planner, interpreter, summarizer, and extractor agents.
    """
    
    def __init__(self):
        self.ssh_client = SSHClient()
        self.context_manager = ContextManager()
        
        # Initialize sub-agents
        self.planner = PlannerAgent()
        self.interpreter = InterpreterAgent()
        self.summarizer = SummarizerAgent() if USE_SUMMARIZER else None
        self.extractor = ExtractorAgent()
        
        # State tracking
        self.current_step = 0
        self.goal_reached = False
        self.attack_in_progress = False
    
    def start_attack(self, goal: str) -> bool:
        """
        Start a new attack with the specified goal
        
        Args:
            goal: The attack goal
            
        Returns:
            True if attack was started successfully, False otherwise
        """
        # Establish SSH connection
        if not self.ssh_client.connect():
            print("Failed to establish SSH connection")
            return False
        
        # Initialize attack context
        self.context_manager.set_attack_goal(goal)
        self.current_step = 0
        self.goal_reached = False
        self.attack_in_progress = True
        
        print(f"Starting attack with goal: {goal}")
        return True
    
    def execute_next_step(self) -> Dict[str, Any]:
        """
        Execute the next step in the attack
        
        Returns:
            Dictionary with step execution results
        """
        if not self.attack_in_progress:
            return {"error": "No attack in progress"}
        
        if self.goal_reached:
            return {"message": "Attack goal already reached"}
        
        if self.current_step >= MAX_ATTACK_STEPS:
            self.attack_in_progress = False
            return {"message": "Maximum attack steps reached, attack terminated"}
        
        # Get the current context
        context = self.context_manager.get_full_context()
        
        # If using summarizer and context is getting large, summarize it
        if self.summarizer and len(context) > 8000:
            summary = self.summarizer.invoke(context)
            context = self.context_manager.get_summarized_context(summary)
        
        # Get the next plan from the planner
        plan = self.planner.invoke(context, self.context_manager.attack_goal)
        self.context_manager.set_current_plan(plan)
        
        # Check if goal is reached according to the planner
        if plan.get("goal_reached", False):
            self.goal_reached = True
            self.attack_in_progress = False
            return {
                "message": "Attack goal reached",
                "plan": plan,
                "step": self.current_step
            }
        
        # Get the first step from the plan
        if not plan.get("steps"):
            return {"error": "No steps in the attack plan"}
        
        step = plan["steps"][0]
        
        # Convert the step to a command
        command = self.interpreter.invoke(context, step)
        
        # Execute the command
        output, error = self.ssh_client.execute_command(command)
        
        if error:
            print(f"Error executing command: {error}")
            result = f"Error: {error}"
        else:
            result = output
        
        # Record the step
        step_data = {
            "command": command,
            "output": result,
            "plan": step,
            "timestamp": datetime.now().isoformat()
        }
        
        self.context_manager.add_attack_step(step_data)
        self.current_step += 1
        
        return {
            "command": command,
            "output": result,
            "plan": step,
            "step": self.current_step
        }
    
    def run_attack_loop(self) -> Dict[str, Any]:
        """
        Run the attack loop until the goal is reached or max steps is reached
        
        Returns:
            Dictionary with attack results
        """
        if not self.attack_in_progress:
            return {"error": "No attack in progress"}
        
        start_time = time.time()
        steps_executed = 0
        
        while not self.goal_reached and self.current_step < MAX_ATTACK_STEPS:
            step_result = self.execute_next_step()
            steps_executed += 1
            
            # Print progress
            print(f"Step {self.current_step}: {step_result.get('command', 'N/A')}")
            
            # Optional delay between steps
            time.sleep(1)
        
        # Get the final attack summary and findings
        context = self.context_manager.get_full_context()
        findings = self.extractor.invoke(context)
        
        # Add vulnerabilities to context
        for vuln in findings.get("vulnerabilities", []):
            self.context_manager.add_vulnerability(vuln)
        
        elapsed_time = time.time() - start_time
        
        return {
            "goal": self.context_manager.attack_goal,
            "goal_reached": self.goal_reached,
            "steps_executed": steps_executed,
            "elapsed_time": elapsed_time,
            "findings": findings
        }
    
    def stop_attack(self) -> Dict[str, Any]:
        """
        Stop the current attack
        
        Returns:
            Dictionary with attack results
        """
        if not self.attack_in_progress:
            return {"message": "No attack in progress"}
        
        self.attack_in_progress = False
        
        # Close SSH connection
        self.ssh_client.close()
        
        return {
            "message": "Attack stopped",
            "steps_executed": self.current_step,
            "goal_reached": self.goal_reached
        }
    
    def get_vulnerabilities(self) -> List[Dict[str, Any]]:
        """
        Get all identified vulnerabilities
        
        Returns:
            List of vulnerability dictionaries
        """
        return self.context_manager.vulnerability_findings
    
    def get_attack_history(self) -> List[Dict[str, Any]]:
        """
        Get the full attack history
        
        Returns:
            List of attack steps
        """
        return self.context_manager.attack_history
    
    def __del__(self):
        """Clean up resources when the agent is destroyed"""
        try:
            self.ssh_client.close()
        except:
            pass