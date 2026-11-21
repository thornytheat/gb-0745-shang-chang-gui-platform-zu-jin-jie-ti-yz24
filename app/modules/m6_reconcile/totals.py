def summary(rows):
    return {
        "应缴分": sum(row["应缴分"] for row in rows),
        "实缴分": sum(row["实缴分"] for row in rows if row["实缴分"] is not None),
        "差额分": sum(row["差额分"] for row in rows if row["差额分"] is not None),
        "缺单应缴分": sum(row["应缴分"] for row in rows if row["实缴分"] is None),
    }
