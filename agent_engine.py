import os
from google import genai
from google.genai import types
from google.adk.agents import LlmAgent

# CONFIGURATION
# We use the new SDK client which auto-detects GOOGLE_API_KEY
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

FAST_MODEL = "gemini-2.0-flash" 
SMART_MODEL = "gemini-2.0-flash"

# [TOOL DEFINITION]
# The new SDK requires this specific object wrapper for Google Search
search_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# HELPER FUNCTION
def query_agent_with_runner(agent, prompt, tools=None):
    """
    Executes the agent using the NEW google-genai SDK (v1.0+)
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        return "⚠️ Error: GOOGLE_API_KEY not set."

    # Config for the new SDK
    generate_config = types.GenerateContentConfig(
        tools=tools, # Pass the properly formatted tool object here
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY_HIGH"
            ),
        ]
    )
    
    try:
        response = client.models.generate_content(
            model=agent.model,
            contents=prompt,
            config=generate_config
        )
        
        if not response.text:
            return "⚠️ Blocked by Safety Filters or Empty Response."
        return response.text
        
    except Exception as e:
        return f"⚠️ Agent Error: {str(e)}"

# AGENT DEFINITIONS (Same as before)
router_agent = LlmAgent(
    name="intent_router",
    model=FAST_MODEL,
    description="Classifies user intent.",
    instruction="Determine if query is RESTAURANT or GROCERY. Output one word."
)

restaurant_vetter = LlmAgent(
    name="restaurant_vetter",
    model=FAST_MODEL,
    description="Finds and checks restaurants.",
    instruction="""
    You are a dietary safety officer. 
    1. Use Google Search to find REAL restaurants matching location/query.
    2. Check menus/allergens against profile.
    Output: Restaurant Name, Safety Status, and Reasoning.
    """
)

grocery_vetter = LlmAgent(
    name="grocery_vetter",
    model=FAST_MODEL,
    description="Checks grocery items.",
    instruction="""
    You are a product analyst. 
    1. Search for ingredient labels. 
    2. Check against profile.
    Output: Brand/Item Name, Safety Status, and Reasoning.
    """
)

auditor_agent = LlmAgent(
    name="safety_auditor",
    model=SMART_MODEL,
    description="Evaluates the safety report.",
    instruction="Review vetting report. Assign Safety Confidence Score (0-100%) and Warning Label."
)

# MAIN ORCHESTRATOR
def process_user_request(user_query, user_profile, location):
    results = {
        "step_1_intent": "",
        "step_2_vetting": "",
        "step_3_audit": ""
    }

    # Step 1: Route
    intent = query_agent_with_runner(router_agent, f"Query: {user_query}").strip()
    if "RESTAURANT" in intent.upper(): intent = "RESTAURANT"
    elif "GROCERY" in intent.upper(): intent = "GROCERY"
    results["step_1_intent"] = intent

    # Step 2: Vet
    localized_prompt = f"""
    User Query: {user_query}
    Location: {location}
    Dietary Profile: {user_profile}
    Find options and vet them strictly.
    """
    
    # We pass the list containing the new tool object
    tools_to_use = [search_tool]
    
    if intent == "RESTAURANT":
        vetting_report = query_agent_with_runner(restaurant_vetter, localized_prompt, tools=tools_to_use)
    else:
        vetting_report = query_agent_with_runner(grocery_vetter, localized_prompt, tools=tools_to_use)
    
    results["step_2_vetting"] = vetting_report

    # Step 3: Audit
    final_audit = query_agent_with_runner(auditor_agent, f"Review this report:\n{vetting_report}")
    results["step_3_audit"] = final_audit

    return results