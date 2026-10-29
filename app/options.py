"""Choices shown on the lunch profile pages. Edit these lists to change the form;
no other code needs to change.

TODO: confirm faculty names with THWS before going live.
"""

ROLES = {
    "newcomer": ("New to Germany", "I arrived recently and want to meet people who live here"),
    "local": ("Local", "I grew up here, or I've lived in Germany for a year or more"),
}

# Mensa locations of Studierendenwerk Würzburg, per city (swerk-wue.de, Oct 2026).
# (id, name, address). The id is what gets stored; keep it stable.
MENSAS = {
    "Würzburg": [
        ("wue-hubland-sued", "Mensa Campus Hubland Süd", "Am Hubland"),
        ("wue-studentenhaus", "Mensa am Studentenhaus", "Am Studentenhaus"),
        ("wue-roentgenring", "Mensa Röntgenring", "Röntgenring 12"),
        ("wue-josef-schneider", "Mensa Josef-Schneider-Straße", "Josef-Schneider-Straße 9"),
    ],
    "Schweinfurt": [
        ("sw-thws", "Mensa THWS Campus Schweinfurt", "Fritz-Drescher-Straße 1"),
    ],
}
CITIES = list(MENSAS)
MENSA_NAME = {mid: name for city in MENSAS.values() for mid, name, _ in city}
MENSA_CITY = {mid: c for c, ms in MENSAS.items() for mid, _, _ in ms}

FACULTIES = [
    "Applied Natural Sciences & Humanities",
    "Architecture & Civil Engineering",
    "Business Administration",
    "Computer Science & Business Information Systems",
    "Design",
    "Electrical Engineering",
    "Industrial Engineering",
    "Mechanical Engineering",
    "Plastics Engineering & Surveying",
    "Social Work",
    "Other",
]

# (code, label). Labels in each language's own name, so people spot theirs fast.
LANGUAGES = [
    ("en", "English"),
    ("de", "Deutsch"),
    ("es", "Español"),
    ("fr", "Français"),
    ("it", "Italiano"),
    ("pt", "Português"),
    ("tr", "Türkçe"),
    ("ru", "Русский"),
    ("uk", "Українська"),
    ("ar", "العربية"),
    ("hi", "हिन्दी"),
    ("zh", "中文"),
]

# Age sliders. AGE_MAX means "this age or older", so a range ending at AGE_MAX has no upper limit.
AGE_MIN = 18
AGE_MAX = 40
AGE_DEFAULT = 22


def age_label(a: int | None) -> str:
    return "" if a is None else (f"{a}+" if a >= AGE_MAX else str(a))


def age_range_label(lo: int | None, hi: int | None) -> str:
    lo = AGE_MIN if lo is None else lo
    hi = AGE_MAX if hi is None else hi
    if lo <= AGE_MIN and hi >= AGE_MAX:
        return "any age"
    if hi >= AGE_MAX:
        return f"{lo}+"
    return f"{lo}–{hi}"


# At each table, everyone gets a different animal: easier to remember and say
# than a code ("I'm the Fox"), and it's how people pick someone in a report.
ANIMALS = [
    ("fox", "🦊", "Fox"), ("turtle", "🐢", "Turtle"), ("owl", "🦉", "Owl"), ("bee", "🐝", "Bee"),
    ("panda", "🐼", "Panda"), ("penguin", "🐧", "Penguin"), ("octopus", "🐙", "Octopus"), ("hedgehog", "🦔", "Hedgehog"),
    ("koala", "🐨", "Koala"), ("frog", "🐸", "Frog"), ("whale", "🐳", "Whale"), ("parrot", "🦜", "Parrot"),
    ("lion", "🦁", "Lion"), ("otter", "🦦", "Otter"), ("snail", "🐌", "Snail"), ("flamingo", "🦩", "Flamingo"),
]
ANIMAL = {key: (emoji, name) for key, emoji, name in ANIMALS}

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"]
TIMES = ["11:30", "12:30", "13:30"]
SLOTS = [f"{d}-{t}" for d in DAYS for t in TIMES]

# This-or-that questions: (key, option A, option B).
# Answers become shared interests in the matching and conversation starters at the table.
THIS_OR_THAT = [
    ("food", "Döner", "Pizza"),
    ("trip", "Mountains", "Sea"),
    ("rhythm", "Early bird", "Night owl"),
    ("drink", "Coffee", "Tea"),
    ("evening", "Concert", "Movie night"),
    ("pet", "Cats", "Dogs"),
    ("plans", "Plan everything", "Go with the flow"),
]
