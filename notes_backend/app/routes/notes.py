from flask_smorest import Blueprint, abort
from flask.views import MethodView

from ..schemas import NoteCreateSchema, NoteUpdateSchema, NoteOutSchema
from ..services.notes_service import NotesService, CryptoBox, require_env

# Ocean Professional theme meta (used in tags/description)
OCEAN_THEME_NOTES = "Notes endpoints with secure handling (Ocean Professional: primary #2563EB, secondary #F59E0B)."

blp = Blueprint(
    "Notes",
    "notes",
    url_prefix="/notes",
    description=f"CRUD operations for secure notes. {OCEAN_THEME_NOTES}",
)


def _get_service() -> NotesService:
    """Get a singleton NotesService bound to configured CryptoBox."""
    # Cache service on the blueprint object to avoid recreating per request
    svc = getattr(blp, "_svc", None)
    if svc is None:
        key = require_env("NOTES_ENCRYPTION_KEY")
        crypto = CryptoBox(key)
        svc = NotesService(crypto=crypto)
        setattr(blp, "_svc", svc)
    return svc


@blp.route("/")
class NotesCollection(MethodView):
    @blp.response(200, NoteOutSchema(many=True), description="List all notes")
    @blp.doc(summary="List notes", description="Returns all notes sorted by updated_at desc.", tags=["Notes"])
    def get(self):
        return _get_service().list_notes()

    @blp.arguments(NoteCreateSchema)
    @blp.response(201, NoteOutSchema, description="Created note")
    @blp.doc(summary="Create note", description="Create a note with encrypted storage.", tags=["Notes"])
    def post(self, json_data):
        return _get_service().create_note(title=json_data["title"], content=json_data["content"])


@blp.route("/<string:note_id>")
class NotesItem(MethodView):
    @blp.response(200, NoteOutSchema, description="Note details")
    @blp.doc(summary="Get note", description="Get a note by its ID.", tags=["Notes"])
    def get(self, note_id: str):
        note = _get_service().get_note(note_id)
        if not note:
            abort(404, message="Note not found")
        return note

    @blp.arguments(NoteUpdateSchema)
    @blp.response(200, NoteOutSchema, description="Updated note")
    @blp.doc(summary="Update note", description="Update specific fields of a note.", tags=["Notes"])
    def patch(self, json_data, note_id: str):
        note = _get_service().update_note(note_id, json_data.get("title"), json_data.get("content"))
        if not note:
            abort(404, message="Note not found")
        return note

    @blp.response(204, description="Note deleted")
    @blp.doc(summary="Delete note", description="Delete a note by its ID.", tags=["Notes"])
    def delete(self, note_id: str):
        deleted = _get_service().delete_note(note_id)
        if not deleted:
            abort(404, message="Note not found")
        return ""
