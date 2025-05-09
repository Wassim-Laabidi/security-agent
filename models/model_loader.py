from langchain_openai import AzureChatOpenAI
from config.settings import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_DEPLOYMENT_NAME,
    AZURE_EMBEDDING_DEPLOYMENT_NAME,
    AZURE_OPENAI_API_VERSION,
    PLANNER_MODEL,
    INTERPRETER_MODEL,
    SUMMARIZER_MODEL,
    EXTRACTOR_MODEL
)

def load_azure_openai_model(deployment_name, temperature=0.1):
    """
    Load an Azure OpenAI model with specified parameters
    """
    return AzureChatOpenAI(
        api_key=AZURE_OPENAI_API_KEY,
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        azure_deployment=deployment_name,
        api_version=AZURE_OPENAI_API_VERSION,
        temperature=temperature
    )

def get_planner_model():
    """Get the model used for attack planning"""
    return load_azure_openai_model(AZURE_DEPLOYMENT_NAME, temperature=0.2)

def get_interpreter_model():
    """Get the model used for command interpretation"""
    return load_azure_openai_model(AZURE_DEPLOYMENT_NAME, temperature=0.1)

def get_summarizer_model():
    """Get the model used for context summarization"""
    return load_azure_openai_model(AZURE_DEPLOYMENT_NAME, temperature=0.1)

def get_extractor_model():
    """Get the model used for vulnerability extraction and remediation"""
    return load_azure_openai_model(AZURE_DEPLOYMENT_NAME, temperature=0.1)