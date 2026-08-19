"""Department band lookup (reference/department_bands.json) + non-conveyable check.

Shared by the Unloader client (department bands for ICC Drop items). This is a
standalone copy so unloader_client.py doesn't depend on the archived ACL/DAR
app - see archive/old_acl_app/ for that app's own (frozen) copy.
"""
import json
from pathlib import Path

def load_department_bands() -> dict:
    """Load department band info from JSON file."""
    bands_file = Path(__file__).parent.parent / "reference" / "department_bands.json"
    if not bands_file.exists():
        return []
    try:
        with open(bands_file) as f:
            data = json.load(f)
        return data.get("departments", [])
    except Exception as e:
        print(f"[WARNING] Failed to load department bands: {str(e)}")
        return []

def get_contrasting_text_rgb(rgb: list) -> tuple:
    """White text on a black department band, black text on every other color."""
    return (255, 255, 255) if tuple(rgb[:3]) == (0, 0, 0) else (0, 0, 0)

def _normalize_dept_number(raw) -> str:
    """Strip a 'D.' prefix and leading zeros so department numbers compare as plain digits.

    Handles inputs like "D.02", "02", 2, "23.0" (from numeric BQ columns), etc.
    """
    text = str(raw).strip()
    if text.upper().startswith("D."):
        text = text[2:]
    elif text.upper().startswith("D"):
        text = text[1:]
    if "." in text:  # drop decimal remnants like "23.0" -> "23"
        text = text.split(".")[0]
    return text.lstrip("0") or "0"

def get_department_band(dept_number: str) -> dict:
    """Get department band info by department number.

    Codes in department_bands.json can list multiple numbers sharing one color band,
    e.g. "D.05/55/72" or "D.38/40" - every number after the slash must be checked,
    not just the first, or departments like 55/72/40 never match.
    """
    if not dept_number:
        return None
    bands = load_department_bands()
    dept_clean = _normalize_dept_number(dept_number)
    for band in bands:
        for band_number in band.get("code", "").split("/"):
            if _normalize_dept_number(band_number) == dept_clean:
                return band
    return None

def check_non_conveyable(length: str, width: str, height: str) -> tuple:
    """Check if item is non-conveyable based on dimensions."""
    try:
        length_val = float(length) if length else 999
        width_val = float(width) if width else 999
        height_val = float(height) if height else 999

        # Sort dimensions to get longest, middle, smallest
        sides = sorted([length_val, width_val, height_val], reverse=True)
        if sides[0] < 7 or sides[1] < 5 or sides[2] < 2:
            return True, "WORKSTATION: NON-CONVEYABLE", "#dc2626"
    except (ValueError, TypeError):
        pass
    return False, "", ""
