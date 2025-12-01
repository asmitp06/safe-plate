import os
import json
from dotenv import load_dotenv # Import the loader
from google import genai
from google.genai import types
from google.adk.agents import LlmAgent

# [LOAD ENV]
# This looks for a .env file and loads it into os.environ
load_dotenv() 

# CONFIGURATION
# Now this will successfully find the key from your .env file
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

FAST_MODEL = "gemini-2.0-flash" 
SMART_MODEL = "gemini-2.0-flash"

# [TOOL DEFINITION]
search_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# [SCHEMAS]
rec_schema = {
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

auditor_schema = {
    "type": "OBJECT",
    "properties": {
        "overall_score": {"type": "INTEGER", "description": "0-100 Confidence Score"},
        "headline": {"type": "STRING", "description": "Short, punchy verdict (e.g. 'Green Light', 'Proceed with Caution')"},
        "summary_notes": {
            "type": "ARRAY", 
            "items": {"type": "STRING"},
            "description": "3-4 short bullet points explaining the risk or safety."
        }
    }
}

# HELPER FUNCTION
def query_agent_with_runner(agent, prompt, tools=None, json_mode=False, schema=None):
    if not os.environ.get("GOOGLE_API_KEY"):
        return "⚠️ Error: GOOGLE_API_KEY not set. Check your .env file."

    config_args = {
        "tools": tools,
        "temperature": 0.2, 
        "safety_settings": [
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="BLOCK_ONLY_HIGH"
            ),
        ]
    }

    if json_mode:
        config_args["response_mime_type"] = "application/json"
        if schema:
            config_args["response_schema"] = schema

    generate_config = types.GenerateContentConfig(**config_args)
    
    try:
        response = client.models.generate_content(
            model=agent.model,
            contents=prompt,
            config=generate_config
        )
        if not response.text:
            return "[]" if json_mode and schema == rec_schema else "{}"
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
    1. SEARCH GOAL: Find enough valid options to fill a list of 6.
    2. CHECK LOCATION: Reject any result that is NOT in the requested city.
    
    3. SCORING RUBRIC (EVIDENCE-BASED):
       - 95-100 (HIGH SAFETY): The search result mentions a "Dedicated Gluten Free Menu", "Dedicated Kitchen", OR explicitly lists "Gluten Free Food Options".
       - 80-94 (MODERATE): Mentions "Gluten Friendly" items or modifications (e.g. "lettuce wrap available") but lacks a strong "Gluten Free" label.
       - <80 (LOW): No clear safe options found.

    4. EVIDENCE EXTRACTION: For every score, you MUST extract and quote the exact phrase from the search result that justifies the score.
    5. Output strictly in the requested JSON format.
    """
)

grocery_vetter = LlmAgent(
    name="grocery_vetter",
    model=FAST_MODEL,
    description="Checks grocery items.",
    instruction="""
    You are a product analyst. 
    1. Search for specific safe brands/products available in local stores.
    
    2. SCORING RUBRIC (EVIDENCE-BASED):
       - 95-100: Package explicitly states "Certified Gluten Free" or "Certified Allergen Free".
       - 85-94: Product listing claims "Gluten Free" or "No [Allergen]" ingredients (even if not certified).
       - <85: May contain traces / Unsafe.

    3. EVIDENCE EXTRACTION: Quote the label or ingredient claim found in the search text.
    4. Output strictly in the requested JSON format.
    """
)

auditor_agent = LlmAgent(
    name="safety_auditor",
    model=SMART_MODEL,
    description="Evaluates the safety report.",
    instruction="""
    You are a Quality Assurance Auditor. 
    Review the provided list of recommendations.
    1. Assign an overall 'Safety Confidence Score' (0-100).
    2. Write a short 'Headline' (e.g., "Safe to Eat", "High Risk", "Mixed Bag").
    3. Provide 3-4 crisp bullet points summarizing why these are safe or risky.
    Output strict JSON.
    """
)

# MAIN ORCHESTRATOR
def process_user_request(user_query, user_profile, location):
    results = {
        "intent": "",
        "recommendations": [], 
        "audit": {} 
    }

    # Step 1: Route
    intent = query_agent_with_runner(router_agent, f"Query: {user_query}").strip()
    if "RESTAURANT" in intent.upper(): intent = "RESTAURANT"
    elif "GROCERY" in intent.upper(): intent = "GROCERY"
    results["intent"] = intent

    # Step 2: Vet (UPDATED FOR 6 OPTIONS & STRICT LOCATION)
    localized_prompt = f"""
    User Query: {user_query}
    Target City/Location: {location}
    Search Constraint: STRICTLY WITHIN {location} ONLY.
    Dietary Profile: {user_profile}
    
    INSTRUCTIONS:
    1. Search Phase: Identify roughly 10-15 potential candidates within the strictly defined city limits of {location}.
       - Use search terms like "Best gluten free [food] {location}" or "Celiac friendly restaurants {location}".
       - Do NOT look in neighboring towns.
    
    2. Ranking Phase: Evaluate candidates using the EVIDENCE-BASED Scoring Rubric.
       - If they have a dedicated menu or explicit options, Score > 95.
       - Extract quotes to prove it.
    
    3. Output Phase: Return 6 valid matches.
       - **MANDATORY**: You MUST return 6 options if at least 6 valid places exist in the city.
       - If you only find 3 "High Safety" (95%+) options, you MUST include "Moderate Safety" (80-94%) options to reach the count of 6.
       - Only return fewer than 6 if strictly necessary (e.g., small town with absolutely no other options).
       - For each, list specific 'safe_items' and the 'website_url'.
    """
    
    tools_to_use = [search_tool]
    
    if intent == "RESTAURANT":
        raw_json = query_agent_with_runner(restaurant_vetter, localized_prompt, tools=tools_to_use, json_mode=True, schema=rec_schema)
    else:
        raw_json = query_agent_with_runner(grocery_vetter, localized_prompt, tools=tools_to_use, json_mode=True, schema=rec_schema)
    
    try:
        results["recommendations"] = json.loads(raw_json)
    except:
        results["recommendations"] = []

    # Step 3: Audit (STRUCTURED)
    audit_json = query_agent_with_runner(
        auditor_agent, 
        f"Review this list for safety against profile '{user_profile}':\n{raw_json}",
        json_mode=True,
        schema=auditor_schema
    )

    try:
        results["audit"] = json.loads(audit_json)
    except:
        results["audit"] = {
            "overall_score": 0, 
            "headline": "Audit Error", 
            "summary_notes": ["System could not generate a safety audit."]
        }

    return results