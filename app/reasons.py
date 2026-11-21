REASONS = {
    "BAD_CASH": "金额缺失或格式有误",
    "BAD_EVENT": "交易字段无效",
    "CONFLICT": "同流水号内容冲突",
    "DUPLICATE": "相同流水重传",
    "NO_CONTRACT": "销售日没有可用合同",
    "OVERLAP": "合同生效日期重叠",
    "ORPHAN_REFUND": "找不到原销售单",
    "REFUND_EARLY": "退单早于销售日",
    "REFUND_LIMIT": "累计退款超过原款",
    "REFUND_SHOP": "退单柜台与原单不同",
    "AFTER_CUT": "晚于结账截止日",
}


def issue(line, code, key):
    return {"行号": line, "流水号": key, "原因码": code, "说明": REASONS[code]}
