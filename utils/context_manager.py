import json
import os
from typing import Dict, List, Any, Optional
from datetime import datetime
from config.settings import CONTEXT_FILE_PATH, MAX_CONTEXT_LENGTH

class ContextManager:
    """
    Manages the attack context throughout the engagement.
    Stores and retrieves attack history, commands, and outputs.
    """
    
    def __init__(self, context_file: str = CONTEXT_FILE_PATH):
        self.context_file = context_file
        self.attack_history = []
        self.attack_goal = ""
        self.current_plan = {}
        self.vulnerability_findings = []
        self.load_context()
        
    def load_context(self) -> None:
        """Load context from the context file if it exists"""
        if os.path.exists(self.context_file):
            try:
                with open(self.context_file, 'r') as f:
                    data = json.load(f)
                    self.attack_history = data.get('attack_history', [])
                    self.attack_goal = data.get('attack_goal', "")
                    self.current_plan = data.get('current_plan', {})
                    self.vulnerability_findings = data.get('vulnerability_findings', [])
            except (json.JSONDecodeError, IOError) as e:
                print(f"Error loading context file: {str(e)}")
    
    def save_context(self) -> None:
        """Save the current context to the context file"""
        data = {
            'attack_goal': self.attack_goal,
            'attack_history': self.attack_history,
            'current_plan': self.current_plan,
            'vulnerability_findings': self.vulnerability_findings,
            'last_updated': datetime.now().isoformat()
        }
        
        try:
            with open(self.context_file, 'w') as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"Error saving context file: {str(e)}")
    
    def set_attack_goal(self, goal: str) -> None:
        """Set the attack goal and initialize a new context"""
        self.attack_goal = goal
        self.attack_history = []
        self.current_plan = {}
        self.vulnerability_findings = []
        self.save_context()
    
    def add_attack_step(self, step_data: Dict[str, Any]) -> None:
        """
        Add a new attack step to the history
        
        Args:
            step_data: Dictionary containing step information:
                - command: The executed command
                - output: Command output
                - plan: The attack plan for this step
                - timestamp: When this step was executed
        """
        self.attack_history.append(step_data)
        self.save_context()
    
    def set_current_plan(self, plan: Dict[str, Any]) -> None:
        """Set the current attack plan"""
        self.current_plan = plan
        self.save_context()
    
    def add_vulnerability(self, vulnerability: Dict[str, Any]) -> None:
        """
        Add a discovered vulnerability
        
        Args:
            vulnerability: Dictionary containing vulnerability information:
                - type: Type of vulnerability
                - description: Description of the vulnerability
                - evidence: Command outputs that confirm the vulnerability
                - remediation: Suggested remediation steps
        """
        self.vulnerability_findings.append(vulnerability)
        self.save_context()
    
    def get_full_context(self) -> str:
        """
        Get the full context of the attack as a string.
        Includes attack goal, history, and current plan.
        """
        context = f"ATTACK GOAL: {self.attack_goal}\n\n"
        
        if self.attack_history:
            context += "ATTACK HISTORY:\n"
            for i, step in enumerate(self.attack_history):
                context += f"--- Step {i+1} ---\n"
                context += f"Plan: {step.get('plan', 'N/A')}\n"
                context += f"Command: {step.get('command', 'N/A')}\n"
                context += f"Output: {step.get('output', 'N/A')}\n\n"
        
        if self.current_plan:
            context += "CURRENT PLAN:\n"
            for i, step in enumerate(self.current_plan.get('steps', [])):
                context += f"{i+1}. {step}\n"
        
        # Truncate if needed to avoid exceeding model context limits
        if len(context) > MAX_CONTEXT_LENGTH:
            # Keep the goal and trim the history
            goal_part = context.split("\n\n")[0] + "\n\n"
            remaining_length = MAX_CONTEXT_LENGTH - len(goal_part) - 50  # 50 chars buffer
            
            # Get the last part of the context that fits
            trimmed_history = context[len(goal_part):][-remaining_length:]
            
            # Find the first complete step after trimming
            first_step_idx = trimmed_history.find("--- Step ")
            if first_step_idx > 0:
                trimmed_history = trimmed_history[first_step_idx:]
            
            context = goal_part + "[...Context truncated due to length...]\n\n" + trimmed_history
        
        return context
    
    def get_summarized_context(self, summary: str) -> str:
        """
        Replace the full context with a summarized version
        
        Args:
            summary: Summarized attack context
            
        Returns:
            The updated context string
        """
        context = f"ATTACK GOAL: {self.attack_goal}\n\n"
        context += f"ATTACK HISTORY SUMMARY:\n{summary}\n\n"
        
        if self.current_plan:
            context += "CURRENT PLAN:\n"
            for i, step in enumerate(self.current_plan.get('steps', [])):
                context += f"{i+1}. {step}\n"
        
        return context
    
    def reset_context(self) -> None:
        """Reset the attack context"""
        self.attack_history = []
        self.attack_goal = ""
        self.current_plan = {}
        self.vulnerability_findings = []
        self.save_context()