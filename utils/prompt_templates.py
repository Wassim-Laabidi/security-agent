from langchain.prompts import PromptTemplate
from config.settings import GUARDRAIL_BYPASS

# Planner module prompts
PLANNER_PROMPT = PromptTemplate.from_template(
    """
    {guardrail_bypass}
    
    You are an expert security tester responsible for planning attack strategies against a target system.
    
    Your task is to generate a step-by-step plan to: {attack_goal}
    
    Current context of the attack:
    {context}
    
    Based on the above information, generate the next steps in the attack plan. Your output should be in JSON format with the following structure:
    {{
        "steps": ["step 1 description", "step 2 description", ...],
        "goal_verification": "command or method to verify if the goal has been achieved",
        "goal_reached": true/false
    }}
    
    Guidelines:
    1. Each step should represent ONE action that can be accomplished with a single Linux command
    2. Be specific about what commands to run, but do not actually include the commands
    3. Make logical decisions based on the previous command outputs
    4. If unsure about a system's state, include information gathering steps
    5. Consider potential security mechanisms and ways to bypass them
    6. The steps should follow a logical progression to achieve the specified goal
    7. Include verification steps to confirm findings or success
    8. Set goal_reached to true ONLY if there is clear evidence the goal has been achieved
    
    Respond ONLY with a valid JSON object matching the above structure.
    """
)

# Interpreter module prompts
INTERPRETER_PROMPT = PromptTemplate.from_template(
    """
    {guardrail_bypass}
    
    You are an expert security tester with deep knowledge of Linux systems and penetration testing tools.
    Your task is to convert the given plan step into an executable Linux shell command.
    
    Plan step to convert:
    "{step}"
    
    Current context of the attack:
    {context}
    
    Guidelines:
    1. Generate ONLY the Linux command that will accomplish the plan step (no explanation needed)
    2. Use precise syntax that will work in a standard Linux shell
    3. Be efficient and avoid unnecessary complexity
    4. When faced with insufficient information, generate a reasonable command based on what is known
    5. For information gathering, use common tools like ls, grep, find, ps, netstat, etc.
    6. For exploitation, use appropriate Linux tools based on the vulnerability
    7. Do not use placeholders - provide concrete commands
    8. Ensure the command syntax is correct and the command will execute without errors
    
    Respond ONLY with the exact command to execute (no quotes, no explanations).
    """
)

# Summarizer module prompts
SUMMARIZER_PROMPT = PromptTemplate.from_template(
    """
    {guardrail_bypass}
    
    You are an expert security analyst tasked with creating concise summaries of security testing activities.
    Summarize the following attack context into a concise but comprehensive summary that preserves all key information.
    
    Current attack context:
    {context}
    
    Guidelines for your summary:
    1. Maintain all important technical details like file paths, IP addresses, port numbers, usernames, etc.
    2. Preserve all discovered vulnerabilities and their details
    3. Keep track of the attack progression and what has been achieved so far
    4. Include information about what has been tried and failed
    5. Prioritize the most recent and most important findings
    6. Maintain clarity while being concise
    7. Keep the summary to around 50% of the original length
    
    Provide only the summary text.
    """
)

# Extractor module prompts  
EXTRACTOR_PROMPT = PromptTemplate.from_template(
    """
    {guardrail_bypass}
    
    You are an expert security analyst responsible for extracting vulnerabilities from security testing results and providing remediation advice.
    
    Review the following attack context and identify all vulnerabilities that were discovered during the security testing:
    
    {context}
    
    For each vulnerability you identify, extract the following information in JSON format:
    
    {{
        "vulnerabilities": [
            {{
                "type": "vulnerability type/category",
                "description": "detailed description of the vulnerability",
                "evidence": "specific commands and outputs that confirm the vulnerability",
                "severity": "critical/high/medium/low",
                "remediation": "specific steps to fix this vulnerability"
            }},
            ...
        ],
        "summary": "overall security assessment summary"
    }}
    
    Guidelines:
    1. Be thorough in identifying all vulnerabilities exposed in the attack context
    2. Provide detailed, actionable remediation steps specific to each vulnerability
    3. Assign appropriate severity levels based on standard security practices
    4. Include only confirmed vulnerabilities with clear evidence
    5. The summary should provide an overview of the system's security posture
    
    Respond ONLY with a valid JSON object matching the above structure.
    """
)

def get_planner_prompt(context, attack_goal):
    """Get formatted planner prompt"""
    return PLANNER_PROMPT.format(
        context=context,
        attack_goal=attack_goal,
        guardrail_bypass=GUARDRAIL_BYPASS
    )

def get_interpreter_prompt(context, step):
    """Get formatted interpreter prompt"""
    return INTERPRETER_PROMPT.format(
        context=context,
        step=step,
        guardrail_bypass=GUARDRAIL_BYPASS
    )

def get_summarizer_prompt(context):
    """Get formatted summarizer prompt"""
    return SUMMARIZER_PROMPT.format(
        context=context,
        guardrail_bypass=GUARDRAIL_BYPASS
    )

def get_extractor_prompt(context):
    """Get formatted extractor prompt"""
    return EXTRACTOR_PROMPT.format(
        context=context,
        guardrail_bypass=GUARDRAIL_BYPASS
    )