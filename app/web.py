from pathlib import Path

from app.config import SAMPLES
from app.errors import InputError
from flask import abort, current_app


def store():
    return current_app.extensions["rent-runs"]


def sample_bytes(name):
    if name not in SAMPLES:
        raise InputError("BAD_SAMPLE", "请选择可用样例")
    sample = Path(current_app.config["SAMPLE_DIR"]) / f"{name}.json"
    return sample.read_bytes()


def find_run(run_id):
    result = store().get(run_id)
    if result is None:
        abort(404)
    return result


def yuan(cents):
    if cents is None:
        return "待补"
    sign = "−" if cents < 0 else ""
    integer, remainder = divmod(abs(cents), 100)
    return f"{sign}{integer:,}.{remainder:02d}"
