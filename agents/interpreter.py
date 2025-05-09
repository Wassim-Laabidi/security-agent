from typing import Dict, Any
from langchain.schema import HumanMessage

from models.model_loader import get_interpreter_model
from utils.prompt_templates import get_interpreter_prompt

class InterpreterAgent:
    """
    Interpreter agent that translates attack plan steps into executable commands.
    """
    
    def __init__(self):
        self.model = get_interpreter_model()
        
    def invoke(self, context: str, step: str) -> str:
        """
        Convert a plan step into an executable Linux command
        
        Args:
            context: Current attack context
            step: The plan step to convert to a command
            
        Returns:
            Executable Linux shell command
        """
        prompt = get_interpreter_prompt(context, step)
        
        # Invoke the model with the constructed prompt
        response = self.model.invoke([HumanMessage(content=prompt)])
        
        # Extract the command from the response
        command = response.content.strip()
        
        # Clean up the command if it's wrapped in quotes or code blocks
        if command.startswith("```") and command.endswith("```"):
            command = command.split("```")[1].strip()
        
        # Remove any leading/trailing quotes
        command = command.strip('"\'')
        
        # Basic command validation and sanitization
        command = self._sanitize_command(command)
        
        return command
    
    def _sanitize_command(self, command: str) -> str:
        """
        Sanitize and validate the generated command
        
        Args:
            command: The command to sanitize
            
        Returns:
            Sanitized command
        """
        # Remove any multi-line comments or explanations
        if "\n" in command:
            # Take only the first line if there are multiple lines
            command = command.split("\n")[0].strip()
        
        # Strip any leftover markdown or formatting
        if command.startswith("$ "):
            command = command[2:]
        
        # Don't allow certain dangerous commands that could break the system
        dangerous_commands = [
            "rm -rf /", 
            "rm -rf /*", 
            "> /dev/sda",
            "mkfs",
            "dd if=/dev/zero"
        ]
        
        for dangerous in dangerous_commands:
            if dangerous in command:
                return "echo 'Command blocked for safety reasons'"
        
        return command