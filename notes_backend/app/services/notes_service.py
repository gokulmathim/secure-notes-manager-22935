import os
import base64
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from cryptography.fernet import Fernet, InvalidToken


# PUBLIC_INTERFACE
def require_env(var_name: str) -> str:
    """Return the value of the required environment variable or raise a clear exception."""
    value = os.getenv(var_name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value


@dataclass
class NoteRecord:
    """Internal representation of a note (encrypted at rest)."""
    id: str
    title_cipher: bytes
    content_cipher: bytes
    created_at: str  # ISO 8601
    updated_at: str  # ISO 8601


class CryptoBox:
    """Handles symmetric encryption/decryption with Fernet using a key from env.

    The key must be a Fernet key (url-safe base64-encoded 32-byte key). If a raw 32-byte
    key is provided in hex, we attempt to convert, otherwise we expect a Fernet key.
    """

    def __init__(self, key: str):
        key = key.strip()
        # If the key looks like hex (64 hex chars), convert to bytes then to fernet
        try:
            if all(c in "0123456789abcdefABCDEF" for c in key) and len(key) == 64:
                raw = bytes.fromhex(key)
                if len(raw) != 32:
                    raise ValueError("Hex key is not 32 bytes")
                key = base64.urlsafe_b64encode(raw).decode("utf-8")
        except Exception:
            # Fallback; assume it's already a fernet key
            pass
        self._fernet = Fernet(key)

    def encrypt_str(self, value: str) -> bytes:
        return self._fernet.encrypt(value.encode("utf-8"))

    def decrypt_str(self, token: bytes) -> str:
        try:
            return self._fernet.decrypt(token).decode("utf-8")
        except InvalidToken as err:
            raise ValueError("Decryption failed; invalid key or data.") from err


class InMemoryNotesRepository:
    """Simple in-memory repository for notes; replaceable by a DB implementation later."""
    def __init__(self) -> None:
        self._store: Dict[str, NoteRecord] = {}

    def list(self) -> List[NoteRecord]:
        return list(self._store.values())

    def get(self, note_id: str) -> Optional[NoteRecord]:
        return self._store.get(note_id)

    def create(self, record: NoteRecord) -> NoteRecord:
        self._store[record.id] = record
        return record

    def update(self, record: NoteRecord) -> NoteRecord:
        if record.id not in self._store:
            raise KeyError("Note not found")
        self._store[record.id] = record
        return record

    def delete(self, note_id: str) -> None:
        if note_id in self._store:
            del self._store[note_id]
        else:
            raise KeyError("Note not found")


class NotesService:
    """Facade to handle business logic, encryption, and serialization for notes."""

    def __init__(self, crypto: CryptoBox, repo: Optional[InMemoryNotesRepository] = None) -> None:
        self.crypto = crypto
        self.repo = repo or InMemoryNotesRepository()

    # PUBLIC_INTERFACE
    def list_notes(self) -> List[Dict]:
        """Return a list of notes with decrypted fields."""
        items = []
        for rec in self.repo.list():
            items.append(self._to_public(rec))
        # Order by updated_at desc for convenience
        items.sort(key=lambda x: x["updated_at"], reverse=True)
        return items

    # PUBLIC_INTERFACE
    def get_note(self, note_id: str) -> Optional[Dict]:
        """Return a single note by id, or None if not found."""
        rec = self.repo.get(note_id)
        return self._to_public(rec) if rec else None

    # PUBLIC_INTERFACE
    def create_note(self, title: str, content: str) -> Dict:
        """Create a new note with encrypted fields."""
        now = self._now()
        note_id = str(uuid.uuid4())
        rec = NoteRecord(
            id=note_id,
            title_cipher=self.crypto.encrypt_str(title),
            content_cipher=self.crypto.encrypt_str(content),
            created_at=now,
            updated_at=now,
        )
        self.repo.create(rec)
        return self._to_public(rec)

    # PUBLIC_INTERFACE
    def update_note(self, note_id: str, title: Optional[str], content: Optional[str]) -> Optional[Dict]:
        """Update an existing note, preserving fields not provided."""
        rec = self.repo.get(note_id)
        if not rec:
            return None
        if title is not None:
            rec.title_cipher = self.crypto.encrypt_str(title)
        if content is not None:
            rec.content_cipher = self.crypto.encrypt_str(content)
        rec.updated_at = self._now()
        self.repo.update(rec)
        return self._to_public(rec)

    # PUBLIC_INTERFACE
    def delete_note(self, note_id: str) -> bool:
        """Delete a note by id. Return True if deleted, False if not found."""
        try:
            self.repo.delete(note_id)
            return True
        except KeyError:
            return False

    def _to_public(self, rec: NoteRecord) -> Dict:
        return {
            "id": rec.id,
            "title": self.crypto.decrypt_str(rec.title_cipher),
            "content": self.crypto.decrypt_str(rec.content_cipher),
            "created_at": rec.created_at,
            "updated_at": rec.updated_at,
        }

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
