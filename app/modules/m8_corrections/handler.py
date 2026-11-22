from flask import Blueprint, jsonify, request, url_for

from app.config import DEFAULT_PERIOD, MAX_SOURCE_BYTES, SAMPLES
from app.errors import InputError
from app.modules.m8_corrections.correct import run_correction
from app.web import find_run, sample_bytes, store

routes = Blueprint("corrections", __name__)

CORRECTION_KEYS = (
    "补正参数",
    "补正采信",
    "补正隔离",
    "补正重传",
    "原流水留档",
    "柜台出账",
    "正式账单",
    "正式账单合计",
    "挂起柜台",
)


@routes.get("/api/corrections/<run_id>")
def inspect_corrections(run_id):
    run = find_run(run_id)
    return jsonify({key: run[key] for key in CORRECTION_KEYS if key in run})


@routes.post("/api/corrections")
def submit_corrections():
    payload = request.form
    sample = payload.get("sample", "mall")
    if sample not in SAMPLES:
        raise InputError("BAD_SAMPLE", "请选择可用样例")
    period = payload.get("period", DEFAULT_PERIOD)
    if not isinstance(period, str):
        raise InputError("BAD_PERIOD", "账期无效")
    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        raise InputError("NO_CORRECTION", "请上传收银补正文件")
    correction_raw = uploaded.read(MAX_SOURCE_BYTES + 1)
    base_raw = sample_bytes(sample)
    run, reused = run_correction(store(), base_raw, correction_raw, period)
    key = run["运行清单"]["批次"]
    return jsonify(
        id=key,
        reused=reused,
        location=url_for(
            "work", stage="corrections", run=key, sample=sample, reuse="1" if reused else None
        ),
        accepted=len(run["补正采信"]),
        isolated=len(run["补正隔离"]),
        retried=len(run["补正重传"]),
        billable=[row["柜台"] for row in run["正式账单"]],
        suspended=[row["柜台"] for row in run["挂起柜台"]],
        bill_totals=run["正式账单合计"],
    ), 200 if reused else 201
