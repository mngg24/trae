# Backend Architecture Guidelines
- Framework: Use FastAPI (Python) to support native asynchronous loops and background workers.
- Project State: Implement a explicit state machine tracking.
- Context Window: Maximize Max Mode parameters to handle dense pipeline scripts.
**Create an Engineering Skill (The Structured JSON Blueprint):**
   Instruct the chat to create an explicit development skill by typing: *"Create a skill under `.trae/skills/` called `json-blueprint` that enforces strict data outputs."*. 
   Ensure the skill metadata configures the specific payload template outlined in your plan[cite: 1]:
   ```json
   {
     "project_meta": { "topic": "...", "target_duration_seconds": 60 },
     "scenes": [{ "scene_number": 1, "narration_script": "...", "image_generation_prompt": "..." }]
   }