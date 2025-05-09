import json
from typing import Dict, Any, List
from langchain.schema import HumanMessage

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
        prompt = get_planner_prompt(context, attack_goal)
        
        # Invoke the model with the constructed prompt
        response = self.model.invoke([HumanMessage(content=prompt)])
        
        # Extract and parse JSON response
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
            
            # Validate the structure
            if not self._validate_plan(plan):
                raise ValueError("Invalid plan structure")
                
            return plan
            
        except (json.JSONDecodeError, ValueError) as e:
            # If JSON parsing fails, return a simple default plan
            print(f"Error parsing planner response: {str(e)}")
            return {
                "steps": ["Gather more information about the system with basic commands"],
                "goal_verification": "Check if we have enough information to proceed",
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
        
        # Check that all required keys are present
        if not all(key in plan for key in required_keys):
            return False
            
        # Check that steps is a list
        if not isinstance(plan["steps"], list):
            return False
            
        # Check that goal_reached is a boolean
        if not isinstance(plan["goal_reached"], bool):
            return False
            
        # Check that goal_verification is a string
        if not isinstance(plan["goal_verification"], str):
            return False
            
        return True