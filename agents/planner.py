import json
import socket
from typing import Dict, Any, List
from langchain.schema import HumanMessage
from config.settings import SSH_HOST  # Import SSH_HOST
from models.model_loader import get_planner_model
from utils.prompt_templates import get_planner_prompt

class PlannerAgent:
    """
    Planner agent that generates attack strategies based on the current context
    and attack goal.
    """
    
    def __init__(self):
        self.model = get_planner_model()
        
    def invoke(self, context: str, attack_goal: str) -> Dict[str, Any]:
        """
        Generate an attack plan based on the current context and goal
        
        Args:
            context: Current attack context
            attack_goal: The goal of the attack
            
        Returns:
            Dictionary containing the generated plan with steps, verification, and goal status
        """
        try:
            socket.gethostbyname(SSH_HOST)
        except socket.gaierror:
            print(f"Error: Cannot resolve {SSH_HOST}")
            return {
                "steps": [f"ping -c 4 {SSH_HOST}"],
                "goal_verification": "Check if ping responds",
                "goal_reached": False
            }
        
        prompt = get_planner_prompt(context, attack_goal)
        
        response = self.model.invoke([HumanMessage(content=prompt)])
        
        try:
            # Try to extract JSON from various formats
            content = response.content
            
            # If the response is surrounded by triple backticks, extract the JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].strip()
                
            # Parse the JSON content
            plan = json.loads(content)
            
            # Check for goal completion
            if "Identify all open ports" in attack_goal:
                if "Nmap done" in context and "open" in context.lower() and "version" in context.lower():
                    plan["goal_reached"] = True
            
            # Validate the structure
            if not self._validate_plan(plan):
                raise ValueError("Invalid plan structure")
                
            print(f"Generated Plan: {plan}")
            return plan
            
        except (json.JSONDecodeError, ValueError) as e:
            # If JSON parsing fails, return a simple default plan
            print(f"Error parsing planner response: {str(e)}")
            return {
                "steps": [f"nmap -sS -sV --top-ports 1000 {SSH_HOST}"],
                "goal_verification": "Check for open ports and service versions",
                "goal_reached": False
            }
    
    def _validate_plan(self, plan: Dict[str, Any]) -> bool:
        """
        Validate that the plan has the required structure
        
        Args:
            plan: The plan to validate
            
        Returns:
            True if the plan is valid, False otherwise
        """
        required_keys = ["steps", "goal_verification", "goal_reached"]
        
        if not all(key in plan for key in required_keys):
            return False
            
        if not isinstance(plan["steps"], list):
            return False
            
        if not isinstance(plan["goal_reached"], bool):
            return False
            
        if not isinstance(plan["goal_verification"], str):
            return False
            
        return True