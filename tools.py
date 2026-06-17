"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _chat(messages: list[dict], temperature: float = 0.7) -> str:
    """Send messages to Groq and return the response text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.
    """
    listings = load_listings()

    # Apply hard filters first
    if max_price is not None:
        listings = [l for l in listings if l["price"] <= max_price]

    if size is not None:
        size_lower = size.strip().lower()
        listings = [
            l for l in listings
            if size_lower in l.get("size", "").lower()
        ]

    # Score by keyword overlap against title, description, style_tags, category
    keywords = [w.lower() for w in description.split() if len(w) > 1]

    def score(listing: dict) -> int:
        searchable = " ".join([
            listing.get("title", ""),
            listing.get("description", ""),
            listing.get("category", ""),
            " ".join(listing.get("style_tags", [])),
            listing.get("brand", "") or "",
        ]).lower()
        return sum(1 for kw in keywords if kw in searchable)

    scored = [(score(l), l) for l in listings]
    matched = [(s, l) for s, l in scored if s > 0]
    matched.sort(key=lambda x: x[0], reverse=True)

    return [l for _, l in matched]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offers general styling advice for the item.
    """
    item_title = new_item.get("title", "this item")
    item_desc = new_item.get("description", "")
    item_style_tags = ", ".join(new_item.get("style_tags", []))
    item_colors = ", ".join(new_item.get("colors", []))
    item_category = new_item.get("category", "")

    wardrobe_items = wardrobe.get("items", [])

    if not wardrobe_items:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a fashion stylist who specializes in thrifted and secondhand clothing. "
                    "Give practical, specific outfit advice. Be concise — 2-3 sentences max."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"I'm thinking of buying this secondhand item: {item_title}.\n"
                    f"Description: {item_desc}\n"
                    f"Style vibe: {item_style_tags}\n"
                    f"Colors: {item_colors}\n"
                    f"Category: {item_category}\n\n"
                    "I don't have a wardrobe entered yet. Give me general styling advice: "
                    "what kinds of pieces pair well with this, what vibe it suits, and one "
                    "specific outfit idea using common wardrobe staples."
                ),
            },
        ]
    else:
        wardrobe_lines = []
        for w in wardrobe_items:
            tags = ", ".join(w.get("style_tags", []))
            colors = ", ".join(w.get("colors", []))
            notes = w.get("notes") or ""
            line = f"- {w['name']} ({w['category']}) — colors: {colors}, vibe: {tags}"
            if notes:
                line += f" — {notes}"
            wardrobe_lines.append(line)
        wardrobe_text = "\n".join(wardrobe_lines)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a fashion stylist who specializes in thrifted and secondhand clothing. "
                    "Suggest specific, complete outfits using the exact pieces listed. "
                    "Be concise — 2-3 sentences per outfit suggestion, 1-2 outfits total."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"I'm thinking of buying this secondhand item: {item_title}.\n"
                    f"Description: {item_desc}\n"
                    f"Style vibe: {item_style_tags}\n"
                    f"Colors: {item_colors}\n"
                    f"Category: {item_category}\n\n"
                    f"My current wardrobe:\n{wardrobe_text}\n\n"
                    "Suggest 1-2 complete outfits that incorporate the new item with specific "
                    "pieces from my wardrobe. Name the wardrobe pieces by name."
                ),
            },
        ]

    try:
        return _chat(messages, temperature=0.7)
    except Exception as e:
        return f"Could not generate outfit suggestion: {e}"


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, returns a descriptive error message string.
    """
    if not outfit or not outfit.strip():
        return (
            "Error: Cannot generate a fit card without an outfit suggestion. "
            "Please run suggest_outfit first to get styling advice."
        )

    item_title = new_item.get("title", "this thrifted find")
    item_price = new_item.get("price", "")
    item_platform = new_item.get("platform", "a thrift platform")
    price_str = f"${item_price:.2f}" if isinstance(item_price, (int, float)) else str(item_price)

    messages = [
        {
            "role": "system",
            "content": (
                "You write authentic, casual fashion captions for Instagram and TikTok OOTD posts. "
                "Your captions sound like a real person — not a brand or influencer script. "
                "Use lowercase, keep it under 4 sentences, and capture the specific vibe of the outfit. "
                "Mention the item name, price, and platform naturally, once each."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Write me an OOTD caption for this outfit:\n{outfit}\n\n"
                f"The thrifted piece is: {item_title}\n"
                f"I bought it for {price_str} on {item_platform}.\n\n"
                "Make it feel real and specific — not generic. "
                "Vary the tone based on the vibe of the outfit."
            ),
        },
    ]

    try:
        return _chat(messages, temperature=1.0)
    except Exception as e:
        return f"Could not generate fit card: {e}"
