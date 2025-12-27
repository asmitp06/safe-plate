import os
import json
import hashlib
import time
from dotenv import load_dotenv
from google import genai
from google.genai import types
from google.adk.agents import LlmAgent

# [LOAD ENV]
load_dotenv() 

# CONFIGURATION - Using gemini-2.0-flash-exp with proper path
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))

FAST_MODEL = "models/gemini-2.0-flash-exp"  # Experimental 2.0 model
SMART_MODEL = "models/gemini-2.0-flash-exp"  # Experimental 2.0 model

# [CACHING SYSTEM]
# Simple in-memory cache with 1-hour expiration
CACHE = {}
CACHE_EXPIRY = 3600  # 1 hour in seconds

def get_cache_key(user_query, user_profile, location):
    """Generate a unique cache key based on query parameters."""
    combined = f"{user_query.lower().strip()}|{user_profile.lower().strip()}|{location.lower().strip()}"
    return hashlib.md5(combined.encode()).hexdigest()

def get_from_cache(cache_key):
    """Retrieve cached result if it exists and hasn't expired."""
    if cache_key in CACHE:
        cached_data, timestamp = CACHE[cache_key]
        if time.time() - timestamp < CACHE_EXPIRY:
            return cached_data
        else:
            # Remove expired cache entry
            del CACHE[cache_key]
    return None

def save_to_cache(cache_key, data):
    """Save result to cache with current timestamp."""
    CACHE[cache_key] = (data, time.time())

# [TOOL DEFINITION]
search_tool = types.Tool(
    google_search=types.GoogleSearch()
)

# [COMBINED SCHEMA] - Includes both recommendations AND audit in one response
combined_schema = {
    "type": "OBJECT",
    "properties": {
        "intent": {
            "type": "STRING",
            "description": "Either RESTAURANT or GROCERY"
        },
        "recommendations": {
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
        },
        "audit": {
            "type": "OBJECT",
            "properties": {
                "overall_score": {"type": "INTEGER", "description": "0-100 Confidence Score"},
                "headline": {"type": "STRING", "description": "Short, punchy verdict (e.g. 'Green Light', 'Proceed with Caution')"},
                "summary_notes": {
                    "type": "ARRAY", 
                    "items": {"type": "STRING"},
                    "description": "3-4 short bullet points explaining the risk or safety."
                }
            },
            "required": ["overall_score", "headline", "summary_notes"]
        }
    },
    "required": ["intent", "recommendations", "audit"]
}

# [COMBINED AGENT] - Does routing, vetting, AND auditing in ONE call
combined_agent = LlmAgent(
    name="unified_safety_agent",
    model=SMART_MODEL,
    description="Handles intent classification, recommendations, and safety audit.",
    instruction="""
    You are a comprehensive dietary safety assistant that performs three tasks in one:
    
    TASK 1: INTENT CLASSIFICATION
    - Determine if the query is about RESTAURANT or GROCERY
    
    TASK 2: RECOMMENDATIONS (based on intent)
    
    FOR RESTAURANTS:
    1. SEARCH GOAL: Find 6 valid options within the specified location.
    2. LOCATION CHECK: Only include results from the requested city.
    3. SCORING RUBRIC (EVIDENCE-BASED):
       - 95-100 (HIGH SAFETY): Mentions "Dedicated Gluten Free Menu", "Dedicated Kitchen", OR explicitly lists "Gluten Free Food Options".
       - 80-94 (MODERATE): Mentions "Gluten Friendly" items or modifications but lacks strong "Gluten Free" label.
       - <80 (LOW): No clear safe options found.
    4. EVIDENCE: Extract and quote exact phrases that justify each score.
    
    FOR GROCERY:
    1. Search for specific safe brands/products available in local stores.
    2. SCORING RUBRIC:
       - 95-100: Package states "Certified Gluten Free" or "Certified Allergen Free".
       - 85-94: Product claims "Gluten Free" or "No [Allergen]" (not certified).
       - <85: May contain traces / Unsafe.
    3. EVIDENCE: Quote the label or ingredient claim.
    
    TASK 3: SAFETY AUDIT
    - Review your own recommendations
    - Assign overall Safety Confidence Score (0-100)
    - Write short Headline (e.g., "Safe to Eat", "High Risk", "Mixed Bag")
    - Provide 3-4 crisp bullet points explaining safety or risks
    
    Output all three tasks in the required JSON format.
    """
)

# HELPER FUNCTION
def query_agent_with_runner(agent, prompt, tools=None, json_mode=False, schema=None):
    if not os.environ.get("GOOGLE_API_KEY"):
        return None, "⚠️ Error: GOOGLE_API_KEY not set. Check your .env file."

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
            return None, "Empty response from API"
        return response.text, None
    except Exception as e:
        error_msg = str(e)
        # Check if it's a quota error
        if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
            return None, f"⚠️ API Quota Exceeded: {error_msg}"
        return None, f"⚠️ API Error: {error_msg}"

# MAIN ORCHESTRATOR WITH CACHING
def process_user_request(user_query, user_profile, location):
    # Check cache first
    cache_key = get_cache_key(user_query, user_profile, location)
    cached_result = get_from_cache(cache_key)
    
    if cached_result:
        # Return cached result to avoid API call
        return cached_result
    
    # Default result structure
    default_results = {
        "intent": "RESTAURANT",
        "recommendations": [], 
        "audit": {
            "overall_score": 0,
            "headline": "Processing Error",
            "summary_notes": ["Unable to process request. Please try again."]
        }
    }

    # Single unified prompt that handles everything
    unified_prompt = f"""
    User Query: {user_query}
    Target City/Location: {location}
    Search Constraint: STRICTLY WITHIN {location} ONLY.
    Dietary Profile: {user_profile}
    
    INSTRUCTIONS:
    1. Determine if this is a RESTAURANT or GROCERY query.
    
    2. Search Phase: Identify 10-15 potential candidates within {location}.
       - Use search terms like "Best gluten free [food] {location}" or "Celiac friendly restaurants {location}".
       - Do NOT look in neighboring towns.
    
    3. Ranking Phase: Evaluate candidates using the EVIDENCE-BASED Scoring Rubric.
       - Extract quotes to prove each score.
    
    4. Output Phase: Return 6 valid matches.
       - MANDATORY: Return 6 options if at least 6 valid places exist.
       - Include "Moderate Safety" (80-94%) options if needed to reach 6.
       - For each, list specific 'safe_items' and 'website_url'.
    
    5. Audit Phase: Review your recommendations and provide:
       - Overall safety confidence score (0-100)
       - Short headline verdict
       - 3-4 bullet points explaining the assessment
    
    Return everything in the specified JSON format with 'intent', 'recommendations', and 'audit' fields.
    """
    
    # ONE API CALL instead of three
    raw_json, error = query_agent_with_runner(
        combined_agent, 
        unified_prompt, 
        tools=[search_tool], 
        json_mode=True, 
        schema=combined_schema
    )
    
    # Handle API errors
    if error:
        default_results["audit"]["summary_notes"] = [error]
        return default_results
    
    # Handle empty response
    if not raw_json or raw_json.strip() == "":
        default_results["audit"]["summary_notes"] = ["Received empty response from API. Please try again."]
        return default_results
    
    # Try to parse JSON
    try:
        results = json.loads(raw_json)
        
        # Validate and ensure all required fields exist
        if not isinstance(results, dict):
            return default_results
            
        if "intent" not in results:
            results["intent"] = "RESTAURANT"
        if "recommendations" not in results or not isinstance(results["recommendations"], list):
            results["recommendations"] = []
        if "audit" not in results or not isinstance(results["audit"], dict):
            results["audit"] = {
                "overall_score": 0,
                "headline": "Incomplete Response",
                "summary_notes": ["System returned incomplete data."]
            }
        
        # Validate audit structure
        if "overall_score" not in results["audit"]:
            results["audit"]["overall_score"] = 0
        if "headline" not in results["audit"]:
            results["audit"]["headline"] = "Unknown Status"
        if "summary_notes" not in results["audit"] or not isinstance(results["audit"]["summary_notes"], list):
            results["audit"]["summary_notes"] = ["No audit notes available."]
            
    except json.JSONDecodeError as e:
        # JSON parsing failed
        default_results["audit"]["summary_notes"] = [
            f"Failed to parse API response: {str(e)}",
            f"Raw response preview: {raw_json[:100]}..."
        ]
        return default_results
    except Exception as e:
        # Any other error
        default_results["audit"]["summary_notes"] = [f"Unexpected error: {str(e)}"]
        return default_results
    
    # Save to cache before returning
    save_to_cache(cache_key, results)
    
    return results