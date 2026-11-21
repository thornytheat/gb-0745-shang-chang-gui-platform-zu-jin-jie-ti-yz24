from app.web import find_run
from flask import Blueprint, jsonify

routes = Blueprint("intake", __name__)


@routes.get("/api/intake/<run_id>")
def inspect_intake(run_id):
    run = find_run(run_id)
    return jsonify({key: run[key] for key in ("收银行", "隔离", "重复", "截止后")})
