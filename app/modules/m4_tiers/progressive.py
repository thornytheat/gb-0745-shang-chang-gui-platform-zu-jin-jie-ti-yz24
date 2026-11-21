from decimal import ROUND_HALF_UP, Decimal


def charge(net_cents, tiers):
    if net_cents < 0:
        raise ValueError("净销售不可为负")
    detail = []
    low = 0
    numerator = 0
    for ceiling, points in tiers:
        high = min(net_cents, ceiling) if ceiling is not None else net_cents
        if high > low:
            band = high - low
            numerator += band * points
            detail.append({"下界分": low, "计提销售分": band, "万分费率": points})
            low = high
        if low >= net_cents:
            break
    return int((Decimal(numerator) / 10000).quantize(Decimal(1), rounding=ROUND_HALF_UP)), detail
