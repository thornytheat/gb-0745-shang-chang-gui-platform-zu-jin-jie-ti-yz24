# 深度登记 商场柜台租金阶梯

- 规模：中型
- 核心规则：版本保底与累进抽成后，将旧期退单定位到原版本、重新计算应计租金并入本期差额。
- 使用者与流程：商场运营结算员导入收银、合同、免租和缴款四本账，逐柜台核账并留档。

## 功能模块

| 模块 | 使用者动作 | 入口 | 核心文件 | 测试 |
|---|---|---|---|---|
| M1 收银采信 | 上传账簿，隔离坏金额和同号矛盾 | `GET /api/intake/{id}` | `app/modules/m1_intake/service.py` `app/modules/m1_intake/amounts.py` | `tests/test_intake.py` |
| M2 合同版本 | 查销售日的合同与重叠区间 | `GET /api/contracts/{id}` | `app/modules/m2_contracts/versions.py` `app/modules/m2_contracts/service.py` | `tests/test_contracts.py` |
| M3 免租日历 | 查看合同日历、免租日期和保底折算 | `GET /api/calendar/{id}` | `app/modules/m3_calendar/month.py` `app/modules/m3_calendar/service.py` | `tests/test_calendar.py` |
| M4 累进抽成 | 对照档位费用与版本保底 | `GET /api/tiers/{id}` | `app/modules/m4_tiers/progressive.py` `app/modules/m4_tiers/service.py` | `tests/test_tiers.py` |
| M5 退单回冲 | 追原流水，重算旧月应计差 | `GET /api/refunds/{id}` | `app/modules/m5_refunds/credits.py` `app/modules/m5_refunds/service.py` | `tests/test_refunds.py` |
| M6 租金勾稽 | 核对实缴、欠缴与账簿行数 | `GET /api/reconcile/{id}` | `app/modules/m6_reconcile/service.py` `app/modules/m6_reconcile/totals.py` | `tests/test_reconcile.py` |
| M7 结算复核 | 从批次凭证复算、下载证据 | `GET /api/publish/{id}` `POST /api/runs` | `app/modules/m7_publish/service.py` `app/modules/m7_publish/export.py` `app/store.py` | `tests/test_publish.py` |
| M8 收银补正 | 套用补正文件，裁决出账与挂起柜台 | `GET /api/corrections/{id}` `POST /api/corrections` | `app/modules/m8_corrections/service.py` `app/modules/m8_corrections/correct.py` `app/modules/m8_corrections/reader.py` | `tests/test_corrections.py` |

## 补正采信规则（M8）

补正文件仅含 `corrections` 区块，每行用 `id`（补正单号）与 `target`（原流水号）定位。逐条裁决：

1. 字段或金额无法解析 → `CORR_BAD_ROW` / `BAD_CASH` 隔离，不动原账。
2. `target` 在原账簿不存在 → `CORR_NO_TARGET`；补正与原行 `kind` 不符 → `CORR_KIND`；柜台不一致 → `CORR_SHOP`（补正不得变更柜台）。
3. 退单补正的 `origin` 必须指向账簿内的销售单，否则 `CORR_BAD_ORIGIN`。
4. 同一补正单号内容一致算重传（`DUPLICATE`，只算一次），内容不同全部 `CORR_CONFLICT` 隔离。
5. 同一条原流水被多条合格补正指向 → 全部 `CORR_TARGET_BUSY` 隔离；未通过单条校验的补正不占用原流水，不拖累其他补正。
6. 采信的补正**替换**原流水，原行与补正行不并存；被替换原行进 `原流水留档`，全部原始行都保留记录。
7. 被拒绝的补正不改写任何已核对柜台；柜台挂起只由修正后仍存在的隔离行与合同交叠决定，与补正文件里的无关差异无关。
8. 批次身份由原账簿摘要 + 补正文件摘要 + 账期派生；同份补正重跑只复用不新增。补正文件结构损坏时整批拒绝、返回 422，旧批次保留。

出账裁决：无残留隔离与合同交叠的柜台进 `正式账单`，其余进 `挂起柜台`，二者柜台互不重叠；正式账单合计与挂起应缴之和等于全量应缴。

## 陷阱登记

| TRAP | 现象 | 朴素实现会怎样 | 本项目处理 | 处理位置 | 测试 |
|---|---|---|---|---|---|
| TRAP-06 | `mall.json` 含全角千分位 | 金额解析失败 | 归一后严格解析 | `app/modules/m1_intake/amounts.py` | `tests/test_intake.py::test_normalized_thousands` |
| TRAP-07 | `mall.json` 收银金额为 N/A | 当零元销售 | 隔离带原因码 | `app/modules/m1_intake/service.py` | `tests/test_intake.py::test_missing_amount_isolated` |
| TRAP-08 | `mall.json` 柜台号有前导零 | 归并时丢失 | 按字符串处理 | `app/modules/m1_intake/service.py` | `tests/test_intake.py::test_leading_zero_and_long_id` |
| TRAP-10 | 费率产生半分 | 浮点或分档舍入偏差 | 按费率整数分子汇总后统一舍入 | `app/modules/m4_tiers/progressive.py` | `tests/test_tiers.py::test_half_up_precise` |
| TRAP-13 | `mall.json` 退单在原销售前读到 | 当成缺原单 | 按业务日归档后匹配 | `app/modules/m5_refunds/credits.py` | `tests/test_refunds.py::test_out_of_order_matched` |
| TRAP-14 | `mall.json` 重复流水金额有差 | 后写覆盖 | 两条都隔离并保留行号 | `app/modules/m1_intake/service.py` | `tests/test_intake.py::test_conflicts_quarantine_both` |
| TRAP-15 | `mall.json` 金额单位混合 | 误把分计为元 | 归一为整数分 | `app/modules/m1_intake/amounts.py` | `tests/test_intake.py::test_unit_is_applied` |
| TRAP-16 | `clean.json` 剪去尾部 | 误入部分交易 | 拒绝结构断裂 | `app/modules/m1_intake/reader.py` | `tests/test_intake.py::test_truncated_source` |
| TRAP-17 | `mall.json` 旧金额字段 gross | 旧账对应列丢失 | 显式兼容别名 | `app/modules/m1_intake/service.py` | `tests/test_intake.py::test_legacy_alias` |
| TRAP-23 | `mall.json` 合同于当日切换 | 同时计入两个版本 | 合同 `[start,end)` | `app/modules/m2_contracts/versions.py` | `tests/test_contracts.py::test_adjacent_boundaries` |
| TRAP-25 | `mall.json` 存在合同重叠 | 随机采信一版 | 暂停区间内归属并提供冲突区间 | `app/modules/m2_contracts/service.py` | `tests/test_contracts.py::test_overlap_not_guessed` |
| TRAP-30 | 补正指向找不到的原流水 | 当成新增交易入账 | `CORR_NO_TARGET` 隔离并保留原账 | `app/modules/m8_corrections/service.py` | `tests/test_corrections.py::test_each_failure_reason` |
| TRAP-31 | 多条补正抢同一原流水 | 后写覆盖前写 | 全部 `CORR_TARGET_BUSY` 隔离，原流水只算一次 | `app/modules/m8_corrections/service.py` | `tests/test_corrections.py::test_one_correction_per_original` |
| TRAP-32 | 补正试图把销售改到别的柜台 | 改写已核对柜台 | `CORR_SHOP` 隔离，原行保持不变 | `app/modules/m8_corrections/service.py` | `tests/test_corrections.py::test_rejected_corrections_keep_original` |
| TRAP-33 | 补正文件含无关差异 | 拖住或改写已核对柜台 | 失败补正不参与挂起裁决，挂起只看修正后残留问题 | `app/modules/m8_corrections/correct.py` | `tests/test_corrections.py::test_unrelated_failed_corrections_do_not_block_cleared_shop` |
| TRAP-34 | 重跑同一份补正 | 重复生成结果 | 摘要派生批次身份，命中即复用 | `app/modules/m8_corrections/correct.py` | `tests/test_corrections.py::test_run_correction_idempotent` |

## 验算

`clean.json` 中 001 柜台的本月净销售 1400 元。前 1000 元按 10%，后 400 元按 20%，抽成为 180 元。旧期退单使原月应计由 130 调整为 110 元。本期应缴 160 元，与实缴平账。

## 已知不覆盖

单场结算以自然月为周期，适用内置样本所示合同规则。跨币种租金、税额和历史更正审批由外围系统处理。
