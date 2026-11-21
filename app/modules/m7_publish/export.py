import json

from flask import Response


def evidence_pack(run):
    run_id = run["运行清单"]["批次"]
    filename = f"rent-{run_id}.json"
    return Response(
        json.dumps(run, ensure_ascii=False, indent=2) + "\n",
        mimetype="application/json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
