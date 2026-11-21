from app.modules.m2_contracts.versions import version_on
from app.reasons import issue


def bind_sales(contracts, events):
    sales, isolated = {}, []
    for event in events:
        if event["kind"] == "sale":
            version, error = version_on(contracts, event["shop"], event["day"])
            if error:
                isolated.append(issue(event["line"], error, event["id"]))
            else:
                sales[event["id"]] = {**event, "version": version["version"]}
    return sales, isolated


def version_conflicts(contracts):
    conflicts = []
    for index, left in enumerate(contracts):
        for right in contracts[index + 1 :]:
            if left["shop"] != right["shop"] or right["start"] >= left["end"]:
                break
            conflicts.append(
                {
                    "柜台": left["shop"],
                    "版本甲": left["version"],
                    "版本乙": right["version"],
                    "起始": right["start"].isoformat(),
                    "截止": min(left["end"], right["end"]).isoformat(),
                }
            )
    return conflicts
