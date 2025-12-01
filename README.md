# 🥗 Safe-Plate Scout: The Forensic Dietary Concierge

**Capstone Submission for Google AI Agents Intensive 2025**
**Track:** Concierge Agents

## 💡 The Why: Solving "Dietary Anxiety"

For the 10% of the population with strict dietary needs (Celiacs, severe allergies, religious restrictions), finding food isn't just about taste—it's about safety. **Safe-Plate Scout** is a multi-agent system that acts as a forensic dietary concierge. Unlike standard search engines that prioritize popularity, this agent prioritizes **safety verification**.

It uses a "Trust but Verify" architecture: one agent finds the food, and a second "Auditor" agent aggressively checks it for safety risks based on the user's specific profile.

## 🛠️ Key Agentic Features Implemented

This project demonstrates the following advanced agent concepts required for the capstone:

### 1\. Multi-Agent System (Sequential & Hierarchical)

  * **Concept:** We use a team of specialized agents rather than a single generalist model. A **Router** delegates tasks to specialists, and an **Auditor** reviews the work.
  * **Implementation:**
      * `router_agent`: Classifies intent (Restaurant vs. Grocery).
      * `restaurant_vetter` / `grocery_vetter`: Specialists that perform the actual research.
      * `auditor_agent`: A distinct persona that reviews the findings.
  * **Where in Code:** Defined in `agent_engine.py` (Lines 77-133). The orchestration logic in `process_user_request` (Lines 136-193) manages the sequential hand-offs.

### 2\. Built-in Tools (Google Search Grounding)

  * **Concept:** The agents are not limited to their training data. They access real-time information from the web to find current menus, ingredients, and allergen statements.
  * **Implementation:** We utilize the native **Google Search Tool** provided by the Google GenAI SDK.
  * **Where in Code:** Configured in `agent_engine.py`:
    ```python
    search_tool = types.Tool(google_search=types.GoogleSearch())
    ```
    This tool is injected dynamically into the vetting agents during execution.

### 3\. Agent Evaluation (LLM-as-a-Judge)

  * **Concept:** Instead of blindly trusting the search results, we implement a self-correction/evaluation step *before* showing the user the answer.
  * **Implementation:** The `auditor_agent` receives the raw findings from the vetter. It is instructed to act as a "Quality Assurance Auditor," assigning a numerical **Safety Confidence Score (0-100)** and a "Green/Red Light" verdict.
  * **Where in Code:** The `auditor_agent` definition (Lines 122-133) and the final validation step in the orchestrator (Lines 180-190).

### 4\. Context Engineering

  * **Concept:** We dynamically construct prompts to enforce strict constraints (Geofencing) and persona alignment.
  * **Implementation:** The prompt template uses f-strings to inject the `Target City/Location` and strictly enforce a "City Limits" rule to prevent the LLM from hallucinating nearby towns as valid results.
  * **Where in Code:** The `localized_prompt` construction in `agent_engine.py` (Lines 153-169).

### 5\. Agent Deployment

  * **Concept:** Moving from a notebook prototype to a scalable web service.
  * **Implementation:** The agent is wrapped in a **FastAPI** backend and containerized using **Docker** for deployment on **Google Cloud Run**.
  * **Where in Code:** `main.py` (API Server) and `Dockerfile`.

## 🏗️ Architecture

1.  **Frontend (HTML/JS):** A responsive web interface (Tailwind CSS) that captures the user's Location, Dietary Profile, and Mission.
2.  **Backend (FastAPI):** A Python API that handles requests and serves the agent.
3.  **The "Brain" (Gemini 2.0 Flash):**
      * **Input:** "Find gluten-free pizza in Chicago."
      * **Step 1 (Router):** Identifies intent -\> "RESTAURANT".
      * **Step 2 (Vetter):** Searches Google for 10 candidates, filters for safety evidence, and selects the Top 6.
      * **Step 3 (Auditor):** Reviews the selected list and assigns a final Safety Score.
      * **Output:** A structured JSON payload containing the vetted list and the auditor's scorecard.

## 🚀 Setup & Usage

### Prerequisites

  * Python 3.10+
  * Google Cloud API Key (Gemini)

### Installation

1.  Clone the repository.
2.  Create a `.env` file and add your key: `GOOGLE_API_KEY="your_key_here"`
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Running Locally

```bash
uvicorn main:app --reload
```

Visit `http://127.0.0.1:8000` in your browser.

### Deployment (Google Cloud Run)

```bash
gcloud run deploy safe-plate-scout --source . --set-env-vars GOOGLE_API_KEY=YOUR_KEY
```
