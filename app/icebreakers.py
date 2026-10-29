"""Conversation starters for each table, built from what the group shares.

Template-based on purpose: no student data leaves the server (no external AI API).
"""

BY_PICK = {
    ("food", "Döner"): "Team Döner: where's the best one in town, and what's the right order?",
    ("food", "Pizza"): "Team Pizza: which topping will you defend even if everyone disagrees?",
    ("trip", "Mountains"): "Mountain people: best hike near here, or the best one back home?",
    ("trip", "Sea"): "Sea people: which coast do you miss, or dream of visiting?",
    ("rhythm", "Early bird"): "Early birds: what do you do with your mornings that night owls are missing?",
    ("rhythm", "Night owl"): "Night owls: what's the best thing to do in town after 10 pm?",
    ("drink", "Coffee"): "Coffee table: best café near campus? Settle it.",
    ("drink", "Tea"): "Tea table: what's the tea you'd bring someone from your home?",
    ("evening", "Concert"): "Concert fans: the best live show you've ever been to?",
    ("evening", "Movie night"): "Movie night crew: one film everyone at this table should watch?",
    ("pet", "Cats"): "Cat people: photos of your cat (or the cat you wish you had), please.",
    ("pet", "Dogs"): "Dog people: what breed would you get, and what would you name it?",
    ("plans", "Plan everything"): "Planners: what's the one thing on your list for this semester?",
    ("plans", "Go with the flow"): "Go-with-the-flow people: best unplanned day you've had recently?",
}

GENERAL = [
    "What surprised you most about Germany, or about your hometown when you saw it through a visitor's eyes?",
    "What's a word in your language that has no good translation?",
    "Best thing to do in {city} on a free afternoon?",
    "What's one dish from home you'd cook for this table?",
]


def for_table(city: str, shared: list[tuple[str, str, int]], limit: int = 3) -> list[str]:
    out = [BY_PICK[(k, v)] for k, v, _ in shared if (k, v) in BY_PICK]
    for q in GENERAL:
        if len(out) >= limit:
            break
        out.append(q.format(city=city))
    return out[:limit]
