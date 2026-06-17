# FitFindr

FitFindr is an AI-powered secondhand fashion agent. Give it a natural language query — "vintage graphic tee under $30, size M" — and it finds a matching thrifted listing, suggests a complete outfit using your wardrobe, and writes an Instagram-ready caption for the look.

## Setup

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
# or: .venv\Scripts\activate    # Windows Command Prompt

pip install -r requirements.txt
```

Create a `.env` file in the project root (never commit this):
```
GROQ_API_KEY=your_key_here
```

Get a free key at [console.groq.com](https://console.groq.com) — no credit card required.

## Running the App

```bash
python app.py
```

Opens a Gradio UI at `http://localhost:7860`. Type a query, choose a wardrobe, and click **Find it**.

To test the agent directly from the terminal:
```bash
python agent.py
```

To run the test suite:
```bash
pytest tests/
```

## How It Works

### The Three Tools

**`search_listings(description, size, max_price)`**
Searches `data/listings.json` (40 mock secondhand listings) for items matching the query. Filters by price and size first, then scores each remaining listing by keyword overlap against its title, description, category, and style tags. Returns results sorted by relevance, or an empty list if nothing matches.

**`suggest_outfit(new_item, wardrobe)`**
Given a listing and the user's wardrobe, calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfits. If the wardrobe is populated, suggestions name specific wardrobe pieces by name. If the wardrobe is empty, the tool switches to general styling advice instead of crashing.

**`create_fit_card(outfit, new_item)`**
Calls the LLM to write a 2–4 sentence Instagram/TikTok caption for the outfit — casual, specific to the vibe, mentioning the item name, price, and platform once each. Uses temperature=1.0 so the output varies across calls.

### The Planning Loop

`run_agent()` in `agent.py` orchestrates the tools in a conditional sequence:

1. **Parse** — `_parse_query()` uses regex to extract `description`, `size`, and `max_price` from the natural language query.
2. **Search** — calls `search_listings()` with the parsed parameters.
   - If the result is empty → set an error message and **return early**. `suggest_outfit` is never called with empty input.
   - If results exist → select the top result and continue.
3. **Style** — calls `suggest_outfit(selected_item, wardrobe)`.
4. **Caption** — calls `create_fit_card(outfit_suggestion, selected_item)`.
5. **Return** the completed session dict.

The agent does not call all three tools unconditionally — step 2 is the key branch that changes behavior based on what `search_listings` returns.

### State Management

All state lives in a single `session` dict that is mutated in place as the loop progresses. No data is re-entered between steps — the item found by `search_listings` flows directly into `suggest_outfit` and then into `create_fit_card` via `session["selected_item"]` and `session["outfit_suggestion"]`.

### Error Handling

| Tool | Failure mode | Response |
|------|-------------|----------|
| `search_listings` | No listings match | Returns `[]`. The loop sets `session["error"]` with a message explaining what was searched and what to try (raise budget, remove size filter, change keywords). Returns early — `suggest_outfit` is not called. |
| `suggest_outfit` | Wardrobe is empty | Switches to a general-advice LLM prompt. Always returns a non-empty string — never raises an exception. |
| `create_fit_card` | Outfit string is empty | Returns immediately with a descriptive error string. No LLM call is made. |

All three tools catch LLM API exceptions and return a descriptive error string rather than crashing the agent.

## Project Structure

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # load_listings(), get_example_wardrobe(), get_empty_wardrobe()
├── tests/
│   └── test_tools.py          # pytest tests for all three tools and failure modes
├── tools.py                   # search_listings, suggest_outfit, create_fit_card
├── agent.py                   # Planning loop (run_agent) and query parser
├── app.py                     # Gradio UI
├── planning.md                # Design spec, architecture diagram, AI tool plan
└── requirements.txt
```
