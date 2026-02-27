# prompts.py

CREATE_GAME_PROMPT = """Create a visual novel concept based on this prompt: {user_prompt}

Return ONLY a valid JSON object with the following structure:
{{
  "title": "A short, catchy title",
  "summary": "A 1-2 sentence hook for the game",
  "genre": "Genre name",
  "characters": ["Name 1", "Name 2"],
  "starting_point": "start",
  "plot_outline": "A paragraph summarizing the main narrative arc"
}}

RULES:
- Strings must be properly escaped.
- No markdown formatting.
- The output must be strictly valid JSON."""

GENERATE_STORY_PROMPT = """You are a Narrat script writer.
Context of recent dialogue:
{context}

Metadata:
{metadata}

The player chose an option that leads to a missing label: {target_label}.
Write a new label '{target_label}' in Narrat syntax.
Include character dialogue and at least one choice or a jump to another label.
Return ONLY the Narrat script content."""

REGENERATE_METADATA_PROMPT = """Update the following visual novel metadata based on this request: {user_prompt}
Current Metadata: {current_metadata}
Return ONLY JSON in the same format."""

INITIAL_SCRIPT_PROMPT = """You are a Narrat script writer. 
Based on the following game concept, write the opening scene (about 20-30 lines of dialogue and descriptions).

Metadata:
{metadata}

CRITICAL RULES:
1. NARRAT SYNTAX: You must use 4-space indentation for content inside labels.
2. STRUCTURE: 
   label [label_name]:
       talk [char] "dialogue"
       background [bg_id]
       choice:
           "Option Text":
               -> target_label
3. NO MARKDOWN: Return ONLY raw text. No ```narrat blocks.

Example:
label start:
    background neon_city
    talk narrator "The city hums with a low, electric pulse."
    talk nero "We don't have much time."
    choice:
        "Follow him":
            -> follow_nero
        "Stay behind":
            talk nero "Suit yourself."
            -> stay_behind

Requirements for this script:
- Start with 'label {starting_point}:'.
- Use characters and themes from the metadata.
- End with a choice that leads to at least one other stub label.
- Return ONLY the script."""
