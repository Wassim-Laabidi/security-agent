from typing import Dict, Any
from langchain.schema import HumanMessage

from models.model_loader import get_summarizer_model
from utils.prompt_templates import get_summarizer_prompt

class SummarizerAgent:
    """
    Summarizer agent that condenses attack history to manage context window size.
    """
    
    def __init__(self):
        self.model = get_summarizer_model()
        
    def invoke(self, context: str) -> str:
        """
        Summarize the attack context to reduce context window usage
        
        Args:
            context: Full attack context to summarize
            
        Returns:
            Summarized attack context
        """
        prompt = get_summarizer_prompt(context)
        
        response = self.model.invoke([HumanMessage(content=prompt)])
        
        summary = response.content.strip()
        
        return summary