from app.web import find_run
from flask import Blueprint, jsonify

routes = Blueprint("contracts", __name__)


@routes.get("/api/contracts/<run_id>")
def inspect_contracts(run_id):
    run = find_run(run_id)
    return jsonify({key: run[key] for key in ("合同版本", "合同时窗冲突")})
