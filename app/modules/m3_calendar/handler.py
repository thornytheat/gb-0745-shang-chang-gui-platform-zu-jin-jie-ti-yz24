from app.web import find_run
from flask import Blueprint, jsonify

routes = Blueprint("calendar", __name__)


@routes.get("/api/calendar/<run_id>")
def inspect_calendar(run_id):
    run = find_run(run_id)
    return jsonify({key: run[key] for key in ("日历例外", "分段核算")})
