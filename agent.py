"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Usage:
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

import re

from tools import search_listings, suggest_outfit, create_fit_card


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """Initialize and return a fresh session dict for one user interaction."""
    return {
        "query": query,
        "parsed": {},
        "search_results": [],
        "selected_item": None,
        "wardrobe": wardrobe,
        "outfit_suggestion": None,
        "fit_card": None,
        "error": None,
    }


# ── query parser ──────────────────────────────────────────────────────────────

def _parse_query(query: str) -> dict:
    """
    Extract description, size, and max_price from a natural language query
    using regex patterns. Falls back gracefully if a field isn't present.

    Returns a dict with keys: description (str), size (str|None), max_price (float|None).
    """
    # Extract price: "$30", "under $30", "under 30", "30 dollars", etc.
    price_match = re.search(
        r"(?:under|below|max|less than|no more than)?\s*\$?\s*(\d+(?:\.\d+)?)\s*(?:dollars?)?",
        query,
        re.IGNORECASE,
    )
    max_price = float(price_match.group(1)) if price_match else None

    # Extract size: "size M", "in M", "size XL", "size S/M", etc.
    size_match = re.search(
        r"\b(?:size\s+)?([SMLXsmlx]{1,3}|XS|XL|XXL|XXS|S\/M|M\/L|[Ww]\d{2}(?:\s*[Ll]\d{2})?)\b",
        query,
    )
    size = size_match.group(1) if size_match else None

    # Build description: strip price/size tokens to leave the item keywords
    description = query
    if price_match:
        description = description.replace(price_match.group(0), " ")
    if size_match:
        description = re.sub(r"\bsize\s+\S+", "", description, flags=re.IGNORECASE)
        description = description.replace(size_match.group(0), " ")

    # Remove filler phrases
    fillers = [
        r"\bunder\b", r"\bbelow\b", r"\bmax\b", r"\bless than\b",
        r"\bno more than\b", r"\bdollars?\b", r"\blooking for\b",
        r"\bi(?:'m| am) looking\b", r"\bcan you find\b", r"\bfind me\b",
        r"\bi want\b", r"\bi need\b", r"\bsomething like\b",
    ]
    for filler in fillers:
        description = re.sub(filler, " ", description, flags=re.IGNORECASE)

    description = re.sub(r"\s+", " ", description).strip()

    return {"description": description, "size": size, "max_price": max_price}


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict

    Returns:
        The session dict. Check session["error"] first — if not None, the
        interaction ended early and outfit_suggestion / fit_card will be None.

    Planning loop logic:
        1. Parse the query to extract description, size, max_price.
        2. Call search_listings(). If empty → set error, return early.
        3. Select top result → store as selected_item.
        4. Call suggest_outfit(selected_item, wardrobe) → store result.
        5. Call create_fit_card(outfit_suggestion, selected_item) → store result.
        6. Return session.
    """
    # Step 1: Initialize session
    session = _new_session(query, wardrobe)

    # Step 2: Parse the query
    parsed = _parse_query(query)
    session["parsed"] = parsed

    # Step 3: Search for listings
    results = search_listings(
        description=parsed["description"],
        size=parsed["size"],
        max_price=parsed["max_price"],
    )
    session["search_results"] = results

    if not results:
        hints = []
        if parsed["max_price"] is not None:
            hints.append(f"try raising your budget above ${parsed['max_price']:.0f}")
        if parsed["size"] is not None:
            hints.append("try removing the size filter")
        hints.append("try different keywords")
        hint_str = ", or ".join(hints)
        session["error"] = (
            f"No listings found matching '{parsed['description']}'"
            + (f" in size {parsed['size']}" if parsed["size"] else "")
            + (f" under ${parsed['max_price']:.0f}" if parsed["max_price"] else "")
            + f". To find more results, {hint_str}."
        )
        return session

    # Step 4: Select top result
    session["selected_item"] = results[0]

    # Step 5: Suggest outfit
    outfit = suggest_outfit(session["selected_item"], wardrobe)
    session["outfit_suggestion"] = outfit

    # Step 6: Create fit card
    fit_card = create_fit_card(outfit, session["selected_item"])
    session["fit_card"] = fit_card

    # Step 7: Return completed session
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
