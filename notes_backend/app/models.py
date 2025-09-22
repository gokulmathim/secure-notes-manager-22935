from datetime import datetime, timezone
from typing import Optional, List

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Column, String, DateTime, Table, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship, Mapped, mapped_column

db = SQLAlchemy()

# Association table for many-to-many Note <-> Tag
note_tags = Table(
    "note_tags",
    db.metadata,
    Column("note_id", String(36), ForeignKey("notes.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Folder(db.Model):
    """Folder model for organizing notes."""
    __tablename__ = "folders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notes: Mapped[List["Note"]] = relationship("Note", back_populates="folder", cascade="all, delete-orphan")

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


class Tag(db.Model):
    """Tag/Label model for flexible note categorization."""
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    notes: Mapped[List["Note"]] = relationship("Note", secondary=note_tags, back_populates="tags")

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)


class Note(db.Model):
    """Encrypted Note model. Title/content are stored as encrypted blobs of text (base64). 
    content_rich stores rich text JSON (encrypted) to support formatting including bold, italics, underline, bullets, and checklists.
    """
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title_cipher: Mapped[str] = mapped_column(Text, nullable=False)   # base64 text of fernet bytes
    content_cipher: Mapped[str] = mapped_column(Text, nullable=False) # base64 text of fernet bytes (plain text content)
    content_rich_cipher: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # encrypted JSON rich text
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    # Sync fields
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    revision: Mapped[int] = mapped_column(db.Integer, default=0, nullable=False)  # increment on each update

    # Folder relation
    folder_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("folders.id", ondelete="SET NULL"), nullable=True, index=True)
    folder: Mapped[Optional[Folder]] = relationship("Folder", back_populates="notes")

    # Tags relation
    tags: Mapped[List[Tag]] = relationship("Tag", secondary=note_tags, back_populates="notes")

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)
        self.revision = (self.revision or 0) + 1
