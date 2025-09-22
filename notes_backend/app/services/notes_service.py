import os
import base64
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Iterable

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, and_
from sqlalchemy.orm import Session
import json

from ..models import db, Note, Tag


# PUBLIC_INTERFACE
def require_env(var_name: str) -> str:
    """Return the value of the required environment variable or raise a clear exception."""
    value = os.getenv(var_name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {var_name}")
    return value


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

    def encrypt_str(self, value: str) -> str:
        """Encrypt text and return base64 text form (safe for Text columns)."""
        token = self._fernet.encrypt(value.encode("utf-8"))
        return base64.urlsafe_b64encode(token).decode("utf-8")

    def decrypt_str(self, token_text: str) -> str:
        """Decrypt from base64 text to clear string."""
        try:
            token = base64.urlsafe_b64decode(token_text.encode("utf-8"))
            return self._fernet.decrypt(token).decode("utf-8")
        except InvalidToken as err:
            raise ValueError("Decryption failed; invalid key or data.") from err


class NotesService:
    """Facade to handle business logic, encryption, and serialization for notes (SQLAlchemy-backed)."""

    def __init__(self, crypto: CryptoBox) -> None:
        self.crypto = crypto

    # PUBLIC_INTERFACE
    def list_notes(
        self,
        q: Optional[str] = None,
        tags: Optional[List[str]] = None,
        folder_id: Optional[str] = None,
        from_iso: Optional[str] = None,
        to_iso: Optional[str] = None,
        include_deleted: bool = False,
    ) -> List[Dict]:
        """Return a list of notes with decrypted fields and applied filters."""
        with db.session() as session:  # type: ignore
            stmt = select(Note)
            conditions = []
            if not include_deleted:
                conditions.append(Note.deleted.is_(False))
            if folder_id:
                conditions.append(Note.folder_id == folder_id)
            if from_iso:
                try:
                    dt_from = datetime.fromisoformat(from_iso)
                    conditions.append(Note.updated_at >= dt_from)
                except Exception:
                    pass
            if to_iso:
                try:
                    dt_to = datetime.fromisoformat(to_iso)
                    conditions.append(Note.updated_at <= dt_to)
                except Exception:
                    pass
            if q:
                # decrypt in app layer; approximate by fetching then filtering client-side to keep encryption
                # We will fetch all candidates by time/folder/deleted and filter after decrypt.
                pass
            if conditions:
                stmt = stmt.where(and_(*conditions))
            # Tag filter requires join; handle separately
            notes = session.execute(stmt).scalars().all()
            if tags:
                tagset = set([t.strip() for t in tags if t.strip()])
                notes = [n for n in notes if tagset.issubset(set([t.name for t in n.tags]))]

            result = []
            for n in notes:
                pub = self._to_public(n)
                if q:
                    ql = q.lower()
                    if ql not in pub["title"].lower() and ql not in pub["content"].lower():
                        continue
                result.append(pub)
            result.sort(key=lambda x: x["updated_at"], reverse=True)
            return result

    # PUBLIC_INTERFACE
    def get_note(self, note_id: str) -> Optional[Dict]:
        """Return a single note by id, or None if not found."""
        with db.session() as session:  # type: ignore
            n: Optional[Note] = session.get(Note, note_id)
            return self._to_public(n) if n else None

    # PUBLIC_INTERFACE
    def create_note(
        self,
        title: str,
        content: str,
        content_rich: Optional[Dict] = None,
        folder_id: Optional[str] = None,
        tag_names: Optional[List[str]] = None,
    ) -> Dict:
        """Create a new note with encrypted fields and taxonomy."""
        now = datetime.now(timezone.utc)
        note = Note(
            id=str(uuid.uuid4()),
            title_cipher=self.crypto.encrypt_str(title),
            content_cipher=self.crypto.encrypt_str(content),
            content_rich_cipher=self.crypto.encrypt_str(
                "" if content_rich is None else _json_dumps(content_rich)
            ) if content_rich is not None else None,
            created_at=now,
            updated_at=now,
            deleted=False,
            revision=0,
            folder_id=folder_id,
        )
        with db.session() as session:  # type: ignore
            if tag_names:
                note.tags = self._ensure_tags(session, tag_names)
            session.add(note)
            session.commit()
            session.refresh(note)
            return self._to_public(note)

    # PUBLIC_INTERFACE
    def update_note(
        self,
        note_id: str,
        title: Optional[str],
        content: Optional[str],
        content_rich: Optional[Dict],
        folder_id: Optional[str],
        tag_names: Optional[List[str]],
        deleted: Optional[bool] = None,
        expect_revision: Optional[int] = None,
    ) -> Optional[Dict]:
        """Update an existing note with optimistic revision check."""
        with db.session() as session:  # type: ignore
            note: Optional[Note] = session.get(Note, note_id)
            if not note:
                return None
            if expect_revision is not None and expect_revision != note.revision:
                # Conflict: return current server version
                return self._to_public(note)

            if title is not None:
                note.title_cipher = self.crypto.encrypt_str(title)
            if content is not None:
                note.content_cipher = self.crypto.encrypt_str(content)
            if content_rich is not None:
                note.content_rich_cipher = self.crypto.encrypt_str(_json_dumps(content_rich))
            if folder_id is not None:
                note.folder_id = folder_id
            if tag_names is not None:
                note.tags = self._ensure_tags(session, tag_names)
            if deleted is not None:
                note.deleted = bool(deleted)

            note.touch()
            session.add(note)
            session.commit()
            session.refresh(note)
            return self._to_public(note)

    # PUBLIC_INTERFACE
    def delete_note(self, note_id: str) -> bool:
        """Soft-delete note (set deleted flag)."""
        with db.session() as session:  # type: ignore
            note: Optional[Note] = session.get(Note, note_id)
            if not note:
                return False
            note.deleted = True
            note.touch()
            session.add(note)
            session.commit()
            return True

    # PUBLIC_INTERFACE
    def hard_delete_note(self, note_id: str) -> bool:
        """Hard delete note (permanent)."""
        with db.session() as session:  # type: ignore
            note: Optional[Note] = session.get(Note, note_id)
            if not note:
                return False
            session.delete(note)
            session.commit()
            return True

    # PUBLIC_INTERFACE
    def sync_pull(self, since: Optional[str]) -> List[Dict]:
        """Return notes updated after 'since' timestamp for client sync."""
        with db.session() as session:  # type: ignore
            stmt = select(Note)
            if since:
                try:
                    dt = datetime.fromisoformat(since)
                    stmt = stmt.where(Note.updated_at > dt)
                except Exception:
                    pass
            notes = session.execute(stmt).scalars().all()
            return [self._to_public(n) for n in notes]

    # PUBLIC_INTERFACE
    def sync_push(self, client_notes: Iterable[Dict]) -> Dict:
        """Apply client changes; return server state for those IDs.
        If revision mismatches, server wins and the server copy is returned."""
        applied = []
        with db.session() as session:  # type: ignore
            for cn in client_notes:
                nid = cn.get("id")
                if not nid:
                    continue
                existing: Optional[Note] = session.get(Note, nid)
                if existing is None:
                    # create if not exists
                    title = cn.get("title", "")
                    content = cn.get("content", "")
                    content_rich = cn.get("content_rich")
                    folder_id = cn.get("folder_id")
                    tags = cn.get("tags") or []
                    deleted = bool(cn.get("deleted", False))
                    now = datetime.fromisoformat(cn.get("updated_at")) if cn.get("updated_at") else datetime.now(timezone.utc)
                    note = Note(
                        id=nid,
                        title_cipher=self.crypto.encrypt_str(title),
                        content_cipher=self.crypto.encrypt_str(content),
                        content_rich_cipher=self.crypto.encrypt_str(_json_dumps(content_rich)) if content_rich is not None else None,
                        created_at=now,
                        updated_at=now,
                        deleted=deleted,
                        revision=int(cn.get("revision", 0)),
                        folder_id=folder_id,
                    )
                    note.tags = self._ensure_tags(session, tags)
                    session.add(note)
                    applied.append(note)
                else:
                    # compare revision - if client's revision >= server, accept
                    client_rev = int(cn.get("revision", 0))
                    if client_rev >= existing.revision:
                        if "title" in cn:
                            existing.title_cipher = self.crypto.encrypt_str(cn.get("title") or "")
                        if "content" in cn:
                            existing.content_cipher = self.crypto.encrypt_str(cn.get("content") or "")
                        if "content_rich" in cn:
                            cr = cn.get("content_rich")
                            existing.content_rich_cipher = self.crypto.encrypt_str(_json_dumps(cr)) if cr is not None else None
                        if "folder_id" in cn:
                            existing.folder_id = cn.get("folder_id")
                        if "tags" in cn:
                            existing.tags = self._ensure_tags(session, cn.get("tags") or [])
                        if "deleted" in cn:
                            existing.deleted = bool(cn.get("deleted"))
                        # Use client's updated_at if provided, else now
                        try:
                            existing.updated_at = datetime.fromisoformat(cn.get("updated_at"))
                        except Exception:
                            existing.touch()
                        existing.revision = client_rev + 1
                    # else: keep server copy unchanged
                    applied.append(existing)
            session.commit()
            # Convert to public after commit
            return {"notes": [self._to_public(n) for n in applied]}

    def _ensure_tags(self, session: Session, tag_names: List[str]) -> List[Tag]:
        """Ensure Tag rows exist for the provided list of names; return Tag objects."""
        cleaned = sorted(set([t.strip() for t in tag_names if t and t.strip()]))
        if not cleaned:
            return []
        existing = session.execute(select(Tag).where(Tag.name.in_(cleaned))).scalars().all()
        existing_map = {t.name: t for t in existing}
        result = list(existing)
        for name in cleaned:
            if name not in existing_map:
                t = Tag(id=str(uuid.uuid4()), name=name, created_at=self._now_dt(), updated_at=self._now_dt())
                session.add(t)
                result.append(t)
        session.flush()  # ensure IDs
        return result

    def _to_public(self, n: Note) -> Dict:
        content_rich = None
        if n.content_rich_cipher:
            try:
                content_rich = _json_loads(self.crypto.decrypt_str(n.content_rich_cipher))
            except Exception:
                content_rich = None
        return {
            "id": n.id,
            "title": self.crypto.decrypt_str(n.title_cipher),
            "content": self.crypto.decrypt_str(n.content_cipher),
            "content_rich": content_rich,
            "folder_id": n.folder_id,
            "tags": [t.name for t in n.tags],
            "deleted": bool(n.deleted),
            "revision": int(n.revision or 0),
            "created_at": n.created_at.isoformat(),
            "updated_at": n.updated_at.isoformat(),
        }

    @staticmethod
    def _now_dt():
        return datetime.now(timezone.utc)


def _json_dumps(obj) -> str:
    try:
        return json.dumps(obj, ensure_ascii=False)
    except Exception:
        return "{}"


def _json_loads(text: str):
    try:
        return json.loads(text)
    except Exception:
        return None

