# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the mock listings dataset for secondhand items that match a keyword description, an optional size filter, and an optional price ceiling. Returns results sorted by keyword relevance (most relevant first).

**Input parameters:**
- `description` (str): Natural language keywords describing the item (e.g., "vintage graphic tee"). Used to score each listing by keyword overlap against title, description, category, and style_tags.
- `size` (str | None): Size string to filter by — matched case-insensitively as a substring of the listing's size field (e.g., "M" matches "S/M" and "M"). Pass `None` to skip size filtering.
- `max_price` (float | None): Maximum price in dollars (inclusive). Listings above this price are excluded. Pass `None` to skip price filtering.

**What it returns:**
A `list[dict]` — each dict is a full listing record with fields:
- `id` (str): unique identifier (e.g., "lst_001")
- `title` (str): short name of the listing
- `description` (str): longer description of the item
- `category` (str): one of tops / bottoms / outerwear / shoes / accessories
- `style_tags` (list[str]): vibe tags (e.g., ["vintage", "grunge"])
- `size` (str): size label (e.g., "M", "W30 L30")
- `condition` (str): one of excellent / good / fair
- `price` (float): listed price in dollars
- `colors` (list[str]): color names
- `brand` (str | None): brand name, or null
- `platform` (str): one of depop / thredUp / poshmark

Returns an empty list `[]` if no listings pass the filters or score above 0. Never raises an exception.

**What happens if it fails or returns nothing:**
If the result is an empty list, the planning loop sets `session["error"]` to a specific, actionable message — e.g., "No listings found matching 'designer ballgown' in size XXS under $5. Try raising your budget, removing the size filter, or using different keywords." The loop returns the session immediately and does NOT call `suggest_outfit` with empty input.

---

### Tool 2: suggest_outfit

**What it does:**
Given a thrifted item the user is considering buying and their current wardrobe, calls the Groq LLM (llama-3.3-70b-versatile) to suggest 1–2 complete outfit combinations. Handles an empty wardrobe gracefully by offering general styling advice instead.

**Input parameters:**
- `new_item` (dict): A full listing dict (as returned by `search_listings`). The tool uses `title`, `description`, `style_tags`, `colors`, and `category` to build the prompt.
- `wardrobe` (dict): A wardrobe dict with an `items` key containing a list of wardrobe item dicts. Each wardrobe item has: `id`, `name`, `category`, `colors`, `style_tags`, and optional `notes`. The `items` list may be empty.

**What it returns:**
A non-empty `str` with 1–2 outfit suggestions. If the wardrobe is populated, suggestions name specific wardrobe pieces by name. If the wardrobe is empty, the string contains general styling advice: what kinds of items pair well, what vibe the piece suits, and one concrete outfit idea using common wardrobe staples.

**What happens if it fails or returns nothing:**
If `wardrobe["items"]` is empty, the tool switches to a general-advice prompt rather than crashing or returning an empty string. If the LLM call itself fails (e.g., API error), the tool catches the exception and returns a descriptive error string: `"Could not generate outfit suggestion: <error detail>"`. The planning loop continues and passes this string to `create_fit_card`.

---

### Tool 3: create_fit_card

**What it does:**
Calls the Groq LLM to generate a 2–4 sentence Instagram/TikTok-style caption for the outfit. The caption sounds like a real OOTD post — casual, specific to the outfit vibe, and mentions the thrifted item's name, price, and platform once each. Uses a high temperature (1.0) to ensure varied output.

**Input parameters:**
- `outfit` (str): The outfit suggestion string returned by `suggest_outfit`. Must be non-empty.
- `new_item` (dict): The listing dict for the thrifted item. The tool uses `title`, `price`, and `platform` to reference the item in the caption.

**What it returns:**
A `str` — 2–4 sentences that could be used as a social media caption. Sounds authentic and casual, not like a product description. The item name, price, and platform are each mentioned once. Output varies on repeated calls with the same inputs (temperature=1.0).

**What happens if it fails or returns nothing:**
If `outfit` is empty or whitespace-only, the tool immediately returns: `"Error: Cannot generate a fit card without an outfit suggestion. Please run suggest_outfit first to get styling advice."` This avoids a meaningless LLM call. If the LLM call fails, the tool catches the exception and returns: `"Could not generate fit card: <error detail>"`.

---

### Additional Tools (if any)

None for the required implementation. See stretch features section if added.

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop in `run_agent()` follows a sequential, conditional decision tree:

1. **Parse the query** using regex (`_parse_query`). Extract:
   - `description`: keywords after stripping price/size tokens and filler phrases
   - `size`: matched by regex pattern for common size labels (S, M, L, XL, W30 L30, etc.)
   - `max_price`: matched by regex for price patterns like "$30", "under 30", "no more than $40"
   Store result in `session["parsed"]`.

2. **Call `search_listings(description, size, max_price)`**.
   Store result in `session["search_results"]`.

   **Branch on result:**
   - If `results == []` (empty list): set `session["error"]` to an actionable message explaining what was searched and what the user can try. **Return the session immediately.** Do NOT call `suggest_outfit`.
   - If `results` is non-empty: select `results[0]` (highest-relevance item), store in `session["selected_item"]`. Continue to step 3.

3. **Call `suggest_outfit(selected_item, wardrobe)`**.
   Store result string in `session["outfit_suggestion"]`.
   (The tool handles the empty-wardrobe case internally — no branching needed here.)

4. **Call `create_fit_card(outfit_suggestion, selected_item)`**.
   Store result string in `session["fit_card"]`.

5. **Return the session** with all fields populated.

The agent never calls all three tools unconditionally — step 2's branch is the key conditional that changes behavior based on what `search_listings` returns.

---

## State Management

**How does information from one tool get passed to the next?**

All state lives in a single `session` dict initialized by `_new_session(query, wardrobe)`. The dict is mutated in place as the loop progresses:

| Field | Set by | Used by |
|-------|--------|---------|
| `session["query"]` | `_new_session` | `_parse_query` |
| `session["parsed"]` | `_parse_query` | `search_listings` call |
| `session["search_results"]` | `search_listings` call | branch check + `selected_item` selection |
| `session["selected_item"]` | loop (top of `search_results`) | `suggest_outfit`, `create_fit_card`, UI formatter |
| `session["wardrobe"]` | `_new_session` | `suggest_outfit` call |
| `session["outfit_suggestion"]` | `suggest_outfit` call | `create_fit_card` call |
| `session["fit_card"]` | `create_fit_card` call | UI display |
| `session["error"]` | loop (on empty search) | UI display (early return) |

The user never re-enters data between steps. The item found by `search_listings` flows directly into `suggest_outfit` via `session["selected_item"]` — the user only typed their query once.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match the query (empty list) | Sets `session["error"]` to: "No listings found matching '<description>'[in size X][under $Y]. To find more results, try raising your budget, removing the size filter, or using different keywords." Returns session early. `suggest_outfit` is NOT called. |
| suggest_outfit | Wardrobe is empty (`wardrobe["items"] == []`) | Switches to a general-advice LLM prompt — returns styling tips for the item type without referencing specific wardrobe pieces. Never returns an empty string or raises an exception. |
| create_fit_card | Outfit input is empty or whitespace-only | Returns immediately with: "Error: Cannot generate a fit card without an outfit suggestion. Please run suggest_outfit first to get styling advice." No LLM call is made. |

---

## Architecture

```
User query (text)
    │
    ▼
_parse_query(query)
    │  description, size, max_price
    ▼
session["parsed"] ──────────────────────────────────────────────────────┐
    │                                                                    │
    ▼                                                                    │ STATE DICT
search_listings(description, size, max_price)                           │
    │                                                                    │
    ├── results == [] ──► session["error"] = "No listings found..."     │
    │                          │                                        │
    │                          ▼                                        │
    │                     RETURN EARLY ◄─────────────────────────────── │
    │                                                                    │
    │ results = [item, ...]                                              │
    ▼                                                                    │
session["search_results"] = results                                      │
session["selected_item"]  = results[0]                                  │
    │                                                                    │
    ▼                                                                    │
suggest_outfit(selected_item, wardrobe)                                  │
    │                                                                    │
    ├── wardrobe empty ──► general styling advice (LLM)                 │
    │                                                                    │
    └── wardrobe present ► specific outfit combos (LLM)                 │
    │                                                                    │
    ▼                                                                    │
session["outfit_suggestion"] = "..."                                     │
    │                                                                    │
    ▼                                                                    │
create_fit_card(outfit_suggestion, selected_item)                        │
    │                                                                    │
    ├── outfit empty ────► return error message string (no LLM call)    │
    │                                                                    │
    └── outfit present ──► Instagram/TikTok caption (LLM, temp=1.0)    │
    │                                                                    │
    ▼                                                                    │
session["fit_card"] = "..."                                              │
    │                                                                    │
    ▼                                                                    │
RETURN session ◄──────────────────────────────────────────────────────── ┘
    │
    ▼
Gradio UI: format session → display in 3 output panels
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**

- **Tool 1 (`search_listings`):** Used Claude Code with this planning.md Tool 1 spec (inputs, filtering logic, scoring method, empty-list failure mode) to implement the function using `load_listings()`. Verified by running 3 test cases: one with a matching keyword, one with an impossible price filter, and one with a size filter. Checked that all results have `price <= max_price` and `size` substring match.

- **Tool 2 (`suggest_outfit`):** Used Claude Code with the Tool 2 spec (wardrobe format, empty wardrobe branch, LLM prompt structure). Verified by calling with `get_example_wardrobe()` and `get_empty_wardrobe()` — confirmed both paths return non-empty strings and that the output changes based on the wardrobe content.

- **Tool 3 (`create_fit_card`):** Used Claude Code with the Tool 3 spec (caption style, item fields to include, empty-outfit guard, temperature=1.0). Verified by: (a) calling with an empty outfit string — confirmed error message returned without exception; (b) calling 3 times with the same inputs — confirmed output varied across calls.

**Milestone 4 — Planning loop and state management:**

- Used Claude Code with the Planning Loop, State Management, and Architecture diagram sections of this planning.md to implement `run_agent()`. Verified by: (a) running the happy-path CLI test and printing `session["selected_item"]` before `suggest_outfit` — confirmed it's the same dict; (b) running the no-results CLI test and confirming `session["error"]` is non-None and `session["fit_card"]` is None; (c) checking that the loop does not call `suggest_outfit` when `search_results` is empty.

---

## A Complete Interaction (Step by Step)

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1 — Parse the query:**
`_parse_query()` extracts:
- `description`: "vintage graphic tee baggy jeans chunky sneakers" (after stripping price tokens)
- `size`: None (no size mentioned)
- `max_price`: 30.0

These are stored in `session["parsed"]`.

**Step 2 — Search listings:**
`search_listings("vintage graphic tee baggy jeans chunky sneakers", size=None, max_price=30.0)` is called.
It filters to listings ≤ $30, then scores each by keyword overlap with the description keywords ["vintage", "graphic", "tee", "baggy", "jeans", "chunky", "sneakers"].
Returns e.g.: `[{"title": "Faded Band Tee — Washed Black", "price": 22.0, "platform": "depop", ...}, ...]`
This list is stored in `session["search_results"]`. The top item is stored in `session["selected_item"]`.

**Step 3 — Suggest outfit:**
`suggest_outfit(session["selected_item"], wardrobe)` is called.
The wardrobe is the example wardrobe with 10 items (baggy jeans, chunky sneakers, etc.).
The LLM is prompted with the item details and the wardrobe item list.
Returns e.g.: "Pair this faded band tee with your baggy straight-leg dark wash jeans and chunky white sneakers for a classic 90s streetwear look. Roll the sleeves once and tuck the front corner for shape. For a grunge twist, swap the sneakers for your black combat boots and add the vintage denim jacket."
Stored in `session["outfit_suggestion"]`.

**Step 4 — Create fit card:**
`create_fit_card(session["outfit_suggestion"], session["selected_item"])` is called.
The LLM is prompted with the outfit description and item details (title, price=$22.00, platform=depop).
Returns e.g.: "thrifted this faded band tee off depop for $22 and it was literally made for my wide-legs 🖤 paired with baggy dark wash jeans and chunky sneakers — very 90s without trying. full look in stories."
Stored in `session["fit_card"]`.

**Final output to user:**
The Gradio UI displays three panels:
- **Top listing found:** Formatted card with title, price ($22.00), platform (Depop), size, condition, brand, colors, style tags, and description.
- **Outfit idea:** The LLM's 2–3 sentence styling suggestion referencing specific wardrobe pieces by name.
- **Your fit card:** The 2–4 sentence Instagram-style caption ready to copy and share.

**Error path (no-results case):**
If the query were "designer ballgown size XXS under $5", `search_listings` returns `[]`. The loop sets `session["error"]` = "No listings found matching 'designer ballgown' in size XXS under $5. To find more results, try raising your budget, remove the size filter, or use different keywords." The session is returned immediately. The Gradio UI shows the error in the first panel and leaves the other two panels empty.
