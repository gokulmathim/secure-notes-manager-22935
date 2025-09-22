from marshmallow import Schema, fields, validate


class TagSchema(Schema):
    id = fields.String(required=True, description="Unique ID of the tag")
    name = fields.String(required=True, description="Tag name", validate=validate.Length(min=1, max=64))
    created_at = fields.String(required=True, description="Creation timestamp (ISO-8601, UTC)")
    updated_at = fields.String(required=True, description="Last update timestamp (ISO-8601, UTC)")


class FolderSchema(Schema):
    id = fields.String(required=True, description="Unique ID of the folder")
    name = fields.String(required=True, description="Folder name", validate=validate.Length(min=1, max=120))
    created_at = fields.String(required=True, description="Creation timestamp (ISO-8601, UTC)")
    updated_at = fields.String(required=True, description="Last update timestamp (ISO-8601, UTC)")


class NoteBaseSchema(Schema):
    title = fields.String(required=True, description="Title of the note", validate=validate.Length(min=1, max=300))
    content = fields.String(required=True, description="Plain text content of the note", validate=validate.Length(min=0))
    content_rich = fields.Dict(required=False, allow_none=True, description="Rich text JSON (supports bold/italic/underline, bullets, checklists)")
    folder_id = fields.String(required=False, allow_none=True, description="Folder ID this note belongs to")
    tags = fields.List(fields.String(), required=False, description="List of tag names to attach to this note")


class NoteCreateSchema(NoteBaseSchema):
    """Schema for note creation."""


class NoteUpdateSchema(Schema):
    title = fields.String(required=False, description="Title of the note", validate=validate.Length(min=1, max=300))
    content = fields.String(required=False, description="Plain text content of the note", validate=validate.Length(min=0))
    content_rich = fields.Dict(required=False, allow_none=True, description="Rich text JSON (supports formatting)")
    folder_id = fields.String(required=False, allow_none=True, description="Folder ID")
    tags = fields.List(fields.String(), required=False, description="List of tag names to set for this note")
    deleted = fields.Boolean(required=False, description="Soft delete flag for sync")
    revision = fields.Integer(required=False, description="Client-known revision for conflict detection")


class NoteOutSchema(Schema):
    id = fields.String(required=True, description="Unique ID of the note")
    title = fields.String(required=True, description="Title of the note")
    content = fields.String(required=True, description="Plain text content of the note")
    content_rich = fields.Dict(required=False, allow_none=True, description="Rich text JSON")
    folder_id = fields.String(required=False, allow_none=True, description="Folder ID")
    tags = fields.List(fields.String(), required=True, description="List of tag names")
    deleted = fields.Boolean(required=True, description="Soft delete flag")
    revision = fields.Integer(required=True, description="Current server revision")
    created_at = fields.String(required=True, description="Creation timestamp (ISO-8601, UTC)")
    updated_at = fields.String(required=True, description="Last update timestamp (ISO-8601, UTC)")


# Filters and Sync Schemas

class NotesQuerySchema(Schema):
    q = fields.String(required=False, description="Keyword search in title or content (decrypted)")
    tags = fields.String(required=False, description="Comma-separated list of tag names to filter")
    folder_id = fields.String(required=False, description="Filter by folder ID")
    from_ = fields.String(data_key="from", required=False, description="Updated at from (ISO-8601)")
    to = fields.String(required=False, description="Updated at to (ISO-8601)")
    include_deleted = fields.Boolean(required=False, missing=False, description="Include soft-deleted notes")


class SyncPullQuerySchema(Schema):
    since = fields.String(required=False, description="Return notes updated after this ISO-8601 timestamp")


class ClientNoteSchema(Schema):
    id = fields.String(required=True)
    title = fields.String(required=True)
    content = fields.String(required=True)
    content_rich = fields.Dict(required=False, allow_none=True)
    folder_id = fields.String(required=False, allow_none=True)
    tags = fields.List(fields.String(), required=False)
    deleted = fields.Boolean(required=True)
    revision = fields.Integer(required=True)
    updated_at = fields.String(required=True)


class SyncPushSchema(Schema):
    notes = fields.List(fields.Nested(ClientNoteSchema), required=True, description="Client changes to reconcile")


class TagCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=64), description="Tag name")


class FolderCreateSchema(Schema):
    name = fields.String(required=True, validate=validate.Length(min=1, max=120), description="Folder name")


class FolderUpdateSchema(Schema):
    name = fields.String(required=False, validate=validate.Length(min=1, max=120), description="Folder name")
