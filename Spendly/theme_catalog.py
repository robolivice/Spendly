DEFAULT_THEME = "fintech"

THEMES = [
    {
        "id": "fintech",
        "name": "Dark Fintech",
        "mode": "Dark",
        "shell": "Top nav",
        "tagline": "Layered ink surfaces and indigo accents.",
        "description": (
            "Layered ink surfaces, indigo gradients, and a top navigation bar. "
            "The calm default for long sessions."
        ),
        "tags": ("Top nav", "Dark first", "Indigo"),
        "meta_color": "#0a0c12",
        "swatch": "linear-gradient(135deg, #0a0c12 42%, #7c9cff)",
        "accent": "#7c9cff",
        "accent_2": "#9a6cff",
    },
    {
        "id": "cockpit",
        "name": "Budget Cockpit",
        "mode": "Dark",
        "shell": "Sidebar",
        "tagline": "A dense telemetry grid with a sidebar cockpit.",
        "description": (
            "A sidebar workspace with a dense metric grid, progress rings, and "
            "pacing charts. Built for scanning at a glance."
        ),
        "tags": ("Sidebar", "Dense grid", "Telemetry"),
        "meta_color": "#0a0f1c",
        "swatch": "linear-gradient(135deg, #0a0f1c 28%, #4f8cff 62%, #22d3ee)",
        "accent": "#4f8cff",
        "accent_2": "#22d3ee",
    },
    {
        "id": "saas",
        "name": "Light SaaS",
        "mode": "Light",
        "shell": "Top nav",
        "tagline": "White cards, soft shadows, and airy spacing.",
        "description": (
            "Airy white cards, soft shadows, and generous spacing. Familiar SaaS "
            "comfort with a warm teal counterpoint."
        ),
        "tags": ("Light first", "Soft cards", "Spacious"),
        "meta_color": "#f6f8fd",
        "swatch": "linear-gradient(135deg, #ffffff 42%, #4058d8 72%, #0f9488)",
        "accent": "#4058d8",
        "accent_2": "#0f9488",
    },
    {
        "id": "glass",
        "name": "Neon Glass",
        "mode": "Dark",
        "shell": "Floating nav",
        "tagline": "Frosted panels with violet and cyan glow.",
        "description": (
            "Floating pill navigation, frosted panels, and gradient light. The "
            "expressive option when the dashboard is the show."
        ),
        "tags": ("Floating nav", "Glass", "Gradients"),
        "meta_color": "#07070f",
        "swatch": "linear-gradient(135deg, #17102b 30%, #b16cff 65%, #22d3ee)",
        "accent": "#b16cff",
        "accent_2": "#22d3ee",
    },
    {
        "id": "paper",
        "name": "Paper Ledger",
        "mode": "Light",
        "shell": "Top nav",
        "tagline": "Ruled paper, ink green, and monospaced figures.",
        "description": (
            "Warm ruled paper, ink-green headers, and monospaced figures. A "
            "tactile accounts-book feel for people who like their numbers handwritten."
        ),
        "tags": ("Paper", "Serif", "Ledger rules"),
        "meta_color": "#f4edde",
        "swatch": "linear-gradient(135deg, #f4edde 34%, #2f5d4c 70%, #9b3f2f)",
        "accent": "#2f5d4c",
        "accent_2": "#9b3f2f",
    },
    {
        "id": "brutal",
        "name": "Neo Brutal",
        "mode": "Light",
        "shell": "Top nav",
        "tagline": "Thick outlines, hard shadows, unapologetic yellow.",
        "description": (
            "Thick outlines, hard shadows, and unapologetic yellow. Every control "
            "reads like a physical switch. Loud on purpose."
        ),
        "tags": ("Hard shadows", "Thick borders", "Yellow"),
        "meta_color": "#f6f1e7",
        "swatch": "linear-gradient(135deg, #f6f1e7 40%, #ffd60a 40% 66%, #111111 66%)",
        "accent": "#111111",
        "accent_2": "#ffd60a",
    },
    {
        "id": "midnight",
        "name": "Midnight Gold",
        "mode": "Dark",
        "shell": "Top nav",
        "tagline": "Near-black lounges and champagne gold.",
        "description": (
            "Near-black lounges, champagne gold, serif display type, and slow "
            "glows. The private-banking take on a budget tracker."
        ),
        "tags": ("Dark luxury", "Gold", "Serif display"),
        "meta_color": "#0a0d12",
        "swatch": "linear-gradient(135deg, #0a0d12 38%, #b58a3c 68%, #f7e4ae)",
        "accent": "#d8b25f",
        "accent_2": "#b58a3c",
    },
    {
        "id": "aurora",
        "name": "Arctic Aurora",
        "mode": "Dark",
        "shell": "Top nav",
        "tagline": "Polar night lit by mint and periwinkle ribbons.",
        "description": (
            "Polar-night surfaces lit by mint and periwinkle ribbons. Glass "
            "panels, cool air, and a dashboard that seems to glow from underneath."
        ),
        "tags": ("Glass", "Aurora", "Mint + indigo"),
        "meta_color": "#071019",
        "swatch": "linear-gradient(135deg, #071019 32%, #7be0c3 66%, #8e9cff)",
        "accent": "#7be0c3",
        "accent_2": "#8e9cff",
    },
    {
        "id": "ember",
        "name": "Ember",
        "mode": "Dark",
        "shell": "Top nav",
        "tagline": "Charred browns and live orange heat.",
        "description": (
            "Charred browns and live orange heat. Glowing gradients pool beneath "
            "the cards like a fire that is still settling."
        ),
        "tags": ("Warm dark", "Glow", "Orange + red"),
        "meta_color": "#140f0c",
        "swatch": "linear-gradient(135deg, #140f0c 34%, #ff8a4c 70%, #ff4d3d)",
        "accent": "#ff8a4c",
        "accent_2": "#ff4d3d",
    },
    {
        "id": "clay",
        "name": "Desert Clay",
        "mode": "Light",
        "shell": "Top nav",
        "tagline": "Sun-baked sand, terracotta, and sage.",
        "description": (
            "Sun-baked sand, terracotta, and sage. Soft asymmetric corners and "
            "slab-serif headings make the whole app feel hand-built."
        ),
        "tags": ("Earthy", "Terracotta", "Organic corners"),
        "meta_color": "#ece0cf",
        "swatch": "linear-gradient(135deg, #ece0cf 36%, #98502f 70%, #6f7d58)",
        "accent": "#98502f",
        "accent_2": "#6f7d58",
    },
]

THEME_IDS = [theme["id"] for theme in THEMES]
THEMES_BY_ID = {theme["id"]: theme for theme in THEMES}


def get_theme(theme_id):
    return THEMES_BY_ID.get(theme_id, THEMES_BY_ID[DEFAULT_THEME])
