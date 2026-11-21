import os

from app.config import DEFAULT_PERIOD, MAX_SOURCE_BYTES, ROOT, RULE_VERSION, SAMPLES
from app.errors import InputError
from app.modules import STAGES, register
from app.modules.m7_publish.export import evidence_pack
from app.modules.m7_publish.service import run_once
from app.store import RunStore
from app.web import find_run, sample_bytes, store, yuan
from flask import Flask, abort, jsonify, render_template, request, url_for


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(
        DATABASE=os.environ.get("RENT_DB", ROOT / "instance" / "rent.sqlite3"),
        MAX_CONTENT_LENGTH=MAX_SOURCE_BYTES + 32 * 1024,
        SAMPLE_DIR=ROOT / "sample_data",
    )
    if config:
        app.config.update(config)
    app.json.ensure_ascii = False
    app.extensions["rent-runs"] = RunStore(app.config["DATABASE"])
    app.jinja_env.filters["yuan"] = yuan
    register(app)

    @app.get("/health")
    def health():
        return {"status": "ok", "version": RULE_VERSION}

    @app.errorhandler(InputError)
    def bad_input(error):
        status = 413 if error.code == "TOO_LARGE" else 422
        return jsonify(code=error.code, detail=str(error)), status

    @app.errorhandler(413)
    def too_large(error):
        return jsonify(code="TOO_LARGE", detail="文件超过 256 KiB"), 413

    @app.get("/")
    @app.get("/work/<stage>")
    def work(stage="reconcile"):
        stage_titles = {slug: label for slug, label, _ in STAGES}
        if stage not in stage_titles:
            abort(404)
        chosen = request.args.get("run")
        if chosen:
            run = find_run(chosen)
        else:
            run, _ = run_once(store(), sample_bytes("mall"), DEFAULT_PERIOD)
        keys = {
            "intake": ("收银行", "隔离", "重复", "截止后"),
            "contracts": ("合同版本", "合同时窗冲突"),
            "calendar": ("日历例外", "分段核算"),
            "tiers": ("分段核算",),
            "refunds": ("旧期回冲", "退单证据"),
            "reconcile": ("柜台对账",),
            "publish": (),
        }[stage]
        return render_template(
            f"{stage}.html",
            active=stage,
            title=stage_titles[stage],
            stages=STAGES,
            run=run,
            meta=run["运行清单"],
            keys=keys,
            samples=SAMPLES,
            sample=request.args.get("sample", "mall"),
            reused=request.args.get("reuse"),
            history=store().history() if stage == "publish" else [],
        )

    @app.get("/api/runs")
    def history():
        return jsonify(store().history())

    @app.post("/api/runs")
    def execute():
        payload = request.get_json(silent=True) if request.is_json else request.form
        if not hasattr(payload, "get"):
            raise InputError("BAD_REQUEST", "请求字段无效")
        stage = payload.get("stage", "reconcile")
        sample = payload.get("sample", "mall")
        if not isinstance(stage, str) or stage not in {slug for slug, _, _ in STAGES}:
            raise InputError("BAD_STAGE", "业务页无效")
        if not isinstance(sample, str) or sample not in SAMPLES:
            raise InputError("BAD_SAMPLE", "请选择可用样例")
        uploaded = request.files.get("file")
        raw = (
            uploaded.read(MAX_SOURCE_BYTES + 1) if uploaded and uploaded.filename else sample_bytes(sample)
        )
        run, reused = run_once(store(), raw, payload.get("period", DEFAULT_PERIOD))
        key = run["运行清单"]["批次"]
        return jsonify(
            id=key,
            reused=reused,
            location=url_for("work", stage=stage, run=key, sample=sample, reuse="1" if reused else None),
            balance=run["行数勾稽"],
            totals=run["金额勾稽"],
        ), 200 if reused else 201

    @app.get("/api/export/<run_id>")
    def export(run_id):
        return evidence_pack(find_run(run_id))

    return app
