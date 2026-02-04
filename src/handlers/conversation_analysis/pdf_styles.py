from reportlab.lib import colors
from reportlab.lib.units import inch

# -------------------------
# PDF STYLE PRESETS
# -------------------------
# To add a new style: copy an existing one, give it a new key, tweak the values.

STYLES = {
    "default": {
        "label": "Default",
        "description": "Clean blue theme with standard sizing",
        "title": "Conversation Analysis Report",
        "margin": 0.5 * inch,
        "title_font_size": 18,
        "heading_font_size": 14,
        "body_font_size": 10,
        "analysis_font_size": 11,
        "heading_color": colors.darkblue,
        "wrap_threshold": 100,
        "wrap_line_length": 80,
    },
    "minimal": {
        "label": "Minimal",
        "description": "Compact black-and-white, smaller fonts",
        "title": "Conversation Analysis Report",
        "margin": 0.4 * inch,
        "title_font_size": 14,
        "heading_font_size": 12,
        "body_font_size": 9,
        "analysis_font_size": 9,
        "heading_color": colors.black,
        "wrap_threshold": 100,
        "wrap_line_length": 90,
    },
    "professional": {
        "label": "Professional",
        "description": "Larger fonts with dark gray headings",
        "title": "Conversation Analysis Report",
        "margin": 0.6 * inch,
        "title_font_size": 22,
        "heading_font_size": 16,
        "body_font_size": 11,
        "analysis_font_size": 12,
        "heading_color": colors.HexColor("#333333"),
        "wrap_threshold": 100,
        "wrap_line_length": 75,
    },
}

DEFAULT_STYLE = "default"


def get_style(name: str = DEFAULT_STYLE) -> dict:
    """Return a style config by name. Falls back to default if not found."""
    return STYLES.get(name, STYLES[DEFAULT_STYLE])


def list_styles() -> list[dict]:
    """Return all available styles as a JSON-friendly list."""
    return [
        {
            "name": key,
            "label": style["label"],
            "description": style["description"],
        }
        for key, style in STYLES.items()
    ]
