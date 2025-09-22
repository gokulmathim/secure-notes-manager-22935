from flask_smorest import Blueprint, abort
from flask.views import MethodView

from ..schemas import (
    NoteCreateSchema,
    NoteUpdateSchema,
    NoteOutSchema,
    NotesQuerySchema,
    SyncPullQuerySchema,
    SyncPushSchema,
)
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
    @blp.arguments(NotesQuerySchema, location="query")
    @blp.response(200, NoteOutSchema(many=True), description="List all notes with filters")
    @blp.doc(summary="List notes", description="Returns notes sorted by updated_at desc. Supports q, tags, folder_id, from/to, include_deleted.", tags=["Notes"])
    def get(self, args):
        tag_list = None
        if args.get("tags"):
            tag_list = [t.strip() for t in (args.get("tags") or "").split(",") if t.strip()]
        return _get_service().list_notes(
            q=args.get("q"),
            tags=tag_list,
            folder_id=args.get("folder_id"),
            from_iso=args.get("from"),
            to_iso=args.get("to"),
            include_deleted=bool(args.get("include_deleted", False)),
        )

    @blp.arguments(NoteCreateSchema)
    @blp.response(201, NoteOutSchema, description="Created note")
    @blp.doc(summary="Create note", description="Create a note with encrypted storage and taxonomy.", tags=["Notes"])
    def post(self, json_data):
        return _get_service().create_note(
            title=json_data["title"],
            content=json_data["content"],
            content_rich=json_data.get("content_rich"),
            folder_id=json_data.get("folder_id"),
            tag_names=json_data.get("tags"),
        )


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
        note = _get_service().update_note(
            note_id,
            json_data.get("title"),
            json_data.get("content"),
            json_data.get("content_rich"),
            json_data.get("folder_id"),
            json_data.get("tags"),
            json_data.get("deleted"),
            json_data.get("revision"),
        )
        if not note:
            abort(404, message="Note not found")
        return note

    @blp.response(204, description="Note soft-deleted")
    @blp.doc(summary="Delete note", description="Soft delete a note by its ID.", tags=["Notes"])
    def delete(self, note_id: str):
        deleted = _get_service().delete_note(note_id)
        if not deleted:
            abort(404, message="Note not found")
        return ""


@blp.route("/sync")
class NotesSync(MethodView):
    @blp.arguments(SyncPullQuerySchema, location="query")
    @blp.response(200, NoteOutSchema(many=True), description="Notes updated since 'since' timestamp")
    @blp.doc(summary="Sync pull", description="Fetch notes updated since the provided ISO-8601 timestamp.", tags=["Notes"])
    def get(self, args):
        return _get_service().sync_pull(args.get("since"))

    @blp.arguments(SyncPushSchema)
    @blp.response(200, SyncPushSchema, description="Server-applied changes and states for provided notes")
    @blp.doc(summary="Sync push", description="Push client changes with revision to reconcile. Server returns authoritative copies.", tags=["Notes"])
    def post(self, json_data):
        return _get_service().sync_push(json_data.get("notes") or [])
