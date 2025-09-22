from marshmallow import Schema, fields, validate


class NoteBaseSchema(Schema):
    title = fields.String(required=True, description="Title of the note", validate=validate.Length(min=1, max=300))
    content = fields.String(required=True, description="Content of the note", validate=validate.Length(min=0))


class NoteCreateSchema(NoteBaseSchema):
    """Schema for note creation."""


class NoteUpdateSchema(Schema):
    title = fields.String(required=False, description="Title of the note", validate=validate.Length(min=1, max=300))
    content = fields.String(required=False, description="Content of the note", validate=validate.Length(min=0))


class NoteOutSchema(Schema):
    id = fields.String(required=True, description="Unique ID of the note")
    title = fields.String(required=True, description="Title of the note")
    content = fields.String(required=True, description="Content of the note")
    created_at = fields.String(required=True, description="Creation timestamp (ISO-8601, UTC)")
    updated_at = fields.String(required=True, description="Last update timestamp (ISO-8601, UTC)")
