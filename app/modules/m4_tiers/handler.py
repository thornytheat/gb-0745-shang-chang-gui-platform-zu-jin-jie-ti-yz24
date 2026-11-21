from app.web import find_run
from flask import Blueprint, jsonify

routes = Blueprint("tiers", __name__)


@routes.get("/api/tiers/<run_id>")
def inspect_tiers(run_id):
    run = find_run(run_id)
    return jsonify({key: run[key] for key in ("分段核算",)})
