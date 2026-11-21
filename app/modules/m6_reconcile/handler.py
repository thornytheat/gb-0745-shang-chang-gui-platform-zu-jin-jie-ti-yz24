from app.web import find_run
from flask import Blueprint, jsonify

routes = Blueprint("reconcile", __name__)


@routes.get("/api/reconcile/<run_id>")
def inspect_reconcile(run_id):
    run = find_run(run_id)
    return jsonify({key: run[key] for key in ("柜台对账", "行数勾稽", "金额勾稽")})
