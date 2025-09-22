"""Routes package for Secure Notes API.

This module exposes commonly used blueprints for convenient imports.
"""
# PUBLIC_INTERFACE
def get_available_blueprints():
    """Return a mapping of blueprint names to blueprint objects for discovery."""
    try:
        from .health import blp as health
    except Exception:
        health = None
    try:
        from .notes import blp as notes
    except Exception:
        notes = None
    try:
        from .taxonomy import blp as taxonomy
    except Exception:
        taxonomy = None
    return {"health": health, "notes": notes, "taxonomy": taxonomy}
