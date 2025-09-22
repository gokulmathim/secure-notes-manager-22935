# Project Repository

Secure Notes API backend with:
- Rich text notes (encrypted title/content; rich JSON content supported)
- Folders and tags for organization
- Search and filter by keyword, tags, date, and folder
- SQLite persistence by default (override with DATABASE_URL)
- Sync endpoints for offline/online reconciliation
- Theme metadata exposed via /docs/help

Environment (.env):
- NOTES_ENCRYPTION_KEY: required (Fernet key or 64-hex for 32-byte key)
- DATABASE_URL: optional (default sqlite:///notes.db)
- PORT: default 3001

Run:
- python run.py