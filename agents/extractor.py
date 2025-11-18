import json
from typing import Dict, Any, List
from langchain.schema import HumanMessage

from models.model_loader import get_extractor_model
from utils.prompt_templates import get_extractor_prompt

class ExtractorAgent:
    """
    Extractor agent that analyzes attack history to identify vulnerabilities
    and create remediation strategies.
    """
    
    def __init__(self):
        self.model = get_extractor_model()
        
    def invoke(self, context: str) -> Dict[str, Any]:
        """
        Extract vulnerabilities and remediation strategies from attack context
        
        Args:
            context: The full attack context
            
        Returns:
            Dictionary containing identified vulnerabilities and remediation suggestions
        """
        prompt = get_extractor_prompt(context)
        
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
            findings = json.loads(content)
            
            # Validate the structure
            if not self._validate_findings(findings):
                raise ValueError("Invalid findings structure")
                
            return findings
            
        except (json.JSONDecodeError, ValueError) as e:
            # If JSON parsing fails, return a simple default structure
            print(f"Error parsing extractor response: {str(e)}")
            return {
                "vulnerabilities": [],
                "summary": "Unable to extract vulnerabilities from the provided context."
            }
    
    def _validate_findings(self, findings: Dict[str, Any]) -> bool:
        """
        Validate that the findings have the required structure
        
        Args:
            findings: The findings to validate
            
        Returns:
            True if the findings are valid, False otherwise
        """
        if "vulnerabilities" not in findings or "summary" not in findings:
            return False
        
        if not isinstance(findings["vulnerabilities"], list):
            return False
        
        for vuln in findings["vulnerabilities"]:
            required_fields = ["type", "description", "evidence", "severity", "remediation"]
            if not all(field in vuln for field in required_fields):
                return False
        
        return True