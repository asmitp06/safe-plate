# 🥗 Safe-Plate Scout: The Forensic Dietary Concierge

**Capstone Submission for Google AI Agents Intensive 2025**
**Track:** Concierge Agents

![Safe-Plate UI](https://via.placeholder.com/800x400.png?text=Safe-Plate+Scout+Dashboard)

## 💡 The Why: Solving "Dietary Anxiety"
For the 10% of the population living with strict dietary needs—including Ovo-Vegetarians, Celiacs, and those with severe allergies—eating out is never just a leisure activity; it is a research project.

**The Problem:**
* **Trust Gap:** Standard apps like Yelp or Google Maps filter for broad categories like "Vegetarian Friendly," but they fail to answer the critical safety questions: *"Is the vegetable soup made with chicken broth?"* or *"Does this cheese contain animal rennet?"*
* **Mental Load:** A simple lunch decision often requires 15-20 minutes of cross-referencing menus, reading reviews, and calling the restaurant.
* **Risk:** A single mistake in reading the fine print can lead to sickness or a violation of deeply held ethical beliefs.

**The Vision:**
We believe technology should handle the burden of verification. **Safe-Plate Scout** was built to eliminate this anxiety by automating the forensic research required to eat safely.

---

## 🤖 The What: A Forensic Agent System
**Safe-Plate Scout** is not just a search engine; it is a **Hierarchical Multi-Agent System** that acts as a forensic dietary auditor. It automates the entire lifecycle of finding safe food, whether that means booking a table or buying groceries.

### Core Capabilities
1.  **Intelligent Intent Routing:** The system uses natural language understanding to detect if a user wants to *dine out* (Restaurant Track) or *buy ingredients* (Grocery Track) without requiring manual toggles.
2.  **Forensic Menu Analysis:** Unlike standard search, our "Vetter Agent" performs deep-dive analysis on menu descriptions. It hunts for "hidden" non-compliant ingredients (e.g., Lard in beans, Gelatin in desserts) that standard filters miss.
3.  **Safety Auditing:** We implement an **"LLM-as-a-Judge"** architecture. A dedicated "Auditor Agent" (powered by the high-reasoning Gemini 1.5 Pro) reviews the output of the other agents to assign a **Safety Confidence Score**, ensuring no hallucinated safety claims reach the user.

---

## 🏗️ Architecture
This project demonstrates a production-grade **Agentic Microservice** built with Python and the Google Agent Development Kit (ADK).

### The Agent Workflow
1.  **Universal Scout:** A location-aware agent that scans Edison, NJ for highly-rated venues or stores matching the user's query.
2.  **Universal Vetter:** A specialized analytical agent. It takes the candidate list and performs targeted searches against the user's specific **Dietary Profile** (stored in Session Memory).
3.  **Safety Auditor:** The final gatekeeper. It grades the Vetter's report on a scale of 0-100% and flags any remaining ambiguity before the user sees the result.

## 🛠️ Tech Stack & Deployment
* **AI Model:** Gemini 2.0 Flash-Lite (Speed) & Gemini 1.5 Pro (Reasoning/Audit)
* **Framework:** Google ADK (Agent Development Kit)
* **Tools:** Google Search (Grounding), Custom Menu Search logic
* **Deployment:** Dockerized for Google Cloud Run compatibility.

## 🚀 How to Run Locally
1.  Clone the repo.
2.  Add your `GOOGLE_API_KEY` to environment variables.
3.  Run with Docker:
    ```bash
    docker build -t safe-plate .
    docker run -p 8080:8080 -e GOOGLE_API_KEY=your_key safe-plate
    ```
4.  Open `http://localhost:8080` to see the UI.