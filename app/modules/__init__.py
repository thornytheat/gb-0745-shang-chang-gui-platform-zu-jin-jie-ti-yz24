from importlib import import_module

STAGES = (
    ("intake", "收银采信", "m1_intake"),
    ("contracts", "合同版本", "m2_contracts"),
    ("calendar", "免租日历", "m3_calendar"),
    ("tiers", "累进抽成", "m4_tiers"),
    ("refunds", "退单回冲", "m5_refunds"),
    ("reconcile", "租金勾稽", "m6_reconcile"),
    ("publish", "结算复核", "m7_publish"),
    ("corrections", "收银补正", "m8_corrections"),
)


def register(app):
    for _, _, package in STAGES:
        app.register_blueprint(import_module(f"app.modules.{package}.handler").routes)
