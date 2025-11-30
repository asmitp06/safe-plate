import os
import json
from google import genai
from google.genai import types
from google.adk.agents import LlmAgent

# CONFIGURATION
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

FAST_MODEL = "gemini-2.0-flash" 
SMART_MODEL = "gemini-2.0-flash"

# [TOOL DEFINITION]
search_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# [STRUCTURED OUTPUT CONFIG]
# This forces the model to return strict JSON we can parse
response_schema = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "name": {"type": "STRING"},
            "address": {"type": "STRING"},
            "website_url": {"type": "STRING"},
            "safe_items": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Specific dishes or products that match the diet"
            },
            "safety_score": {"type": "INTEGER", "description": "0-100"},
            "reasoning": {"type": "STRING"}
        },
        "required": ["name", "safe_items", "reasoning"]
    }
}

# HELPER FUNCTION
def query_agent_with_runner(agent, prompt, tools=None, json_mode=False):
    """
    Executes the agent using the NEW google-genai SDK (v1.0+)
    """
    if not os.environ.get("GOOGLE_API_KEY"):
        return "⚠️ Error: GOOGLE_API_KEY not set."

    # Config for the new SDK
    config_args = {
        "tools": tools,
        "safety_settings": [
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY_HIGH"
            ),
        ]
    }

    # If asking for structured data (JSON), add the schema
    if json_mode:
        config_args["response_mime_type"] = "application/json"
        config_args["response_schema"] = response_schema

    generate_config = types.GenerateContentConfig(**config_args)
    
    try:
        response = client.models.generate_content(
            model=agent.model,
            contents=prompt,
            config=generate_config
        )
        
        if not response.text:
            return [] if json_mode else "⚠️ Blocked or Empty."
            
        return response.text
        
    except Exception as e:
        return f"⚠️ Agent Error: {str(e)}"

# AGENT DEFINITIONS
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
    1. Find REAL restaurants matching location/query using Google Search.
    2. Identify SPECIFIC dishes (menu items) that fit the profile.
    3. Find the official website or menu URL.
    4. Output strictly in the requested JSON format.
    """
)

grocery_vetter = LlmAgent(
    name="grocery_vetter",
    model=FAST_MODEL,
    description="Checks grocery items.",
    instruction="""
    You are a product analyst. 
    1. Search for specific safe brands/products.
    2. List usage ideas or recipes using these items.
    3. Find product URLs.
    4. Output strictly in the requested JSON format.
    """
)

auditor_agent = LlmAgent(
    name="safety_auditor",
    model=SMART_MODEL,
    description="Evaluates the safety report.",
    instruction="Review these recommendations. Return a short text summary of your confidence in them."
)

# MAIN ORCHESTRATOR
def process_user_request(user_query, user_profile, location):
    results = {
        "intent": "",
        "recommendations": [], # This will now be a list of objects
        "audit": ""
    }

    # Step 1: Route
    intent = query_agent_with_runner(router_agent, f"Query: {user_query}").strip()
    if "RESTAURANT" in intent.upper(): intent = "RESTAURANT"
    elif "GROCERY" in intent.upper(): intent = "GROCERY"
    results["intent"] = intent

    # Step 2: Vet (STRUCTURED)
    localized_prompt = f"""
    User Query: {user_query}
    Location: {location}
    Dietary Profile: {user_profile}
    
    Find at least 3 best options. 
    For each, list specific 'safe_items' (actual dishes or products).
    Provide the 'website_url' if available.
    """
    
    tools_to_use = [search_tool]
    
    # We pass json_mode=True to force the list output
    if intent == "RESTAURANT":
        raw_json = query_agent_with_runner(restaurant_vetter, localized_prompt, tools=tools_to_use, json_mode=True)
    else:
        raw_json = query_agent_with_runner(grocery_vetter, localized_prompt, tools=tools_to_use, json_mode=True)
    
    # Parse the JSON string into real Python objects
    try:
        results["recommendations"] = json.loads(raw_json)
    except:
        results["recommendations"] = []

    # Step 3: Audit
    # We pass the formatted list to the auditor
    final_audit = query_agent_with_runner(auditor_agent, f"Review this list for safety:\n{raw_json}")
    results["audit"] = final_audit

    return results