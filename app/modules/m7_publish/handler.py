from app.web import find_run
from flask import Blueprint, jsonify

routes = Blueprint("publish", __name__)


@routes.get("/api/publish/<run_id>")
def inspect_publish(run_id):
    run = find_run(run_id)
    return jsonify({key: run[key] for key in ("运行清单",)})
