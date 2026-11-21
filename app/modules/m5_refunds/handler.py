from app.web import find_run
from flask import Blueprint, jsonify

routes = Blueprint("refunds", __name__)


@routes.get("/api/refunds/<run_id>")
def inspect_refunds(run_id):
    run = find_run(run_id)
    return jsonify({key: run[key] for key in ("旧期回冲", "退单证据")})
