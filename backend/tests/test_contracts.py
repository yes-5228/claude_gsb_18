"""外包合同与费用结算接口测试：覆盖单位/合同管理、考核扣款计算与双向追溯。"""

from datetime import date, datetime, timedelta

from tests.conftest import full_items


def _create_vendor(client, name="洁美环卫服务有限公司"):
    response = client.post(
        "/api/v1/vendors",
        json={"name": name, "contact_person": "马经理", "contact_phone": "13800000000"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_contract(client, vendor_id, restroom_ids, *, fee=10000.0, start=None, end=None):
    today = date.today()
    response = client.post(
        "/api/v1/contracts",
        json={
            "vendor_id": vendor_id,
            "name": "公厕保洁外包合同",
            "service_scope": "日常保洁与垃圾清运",
            "scope_districts": ["测试区"],
            "start_date": (start or today.replace(day=1)).isoformat(),
            "end_date": (end or date(today.year, 12, 31)).isoformat(),
            "monthly_fee": fee,
            "restroom_ids": restroom_ids,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_vendor_crud_and_delete_guard(client, restroom):
    vendor = _create_vendor(client)
    assert vendor["code"].startswith("WB-")

    listed = client.get("/api/v1/vendors", params={"keyword": "洁美"}).json()
    assert listed["meta"]["total"] == 1

    detail = client.get(f"/api/v1/vendors/{vendor['id']}").json()
    assert detail["contract_count"] == 0

    updated = client.patch(
        f"/api/v1/vendors/{vendor['id']}", json={"contact_person": "王主管"}
    ).json()
    assert updated["contact_person"] == "王主管"

    contract = _create_contract(client, vendor["id"], [restroom["id"]])
    # 名下存在合同时禁止删除单位
    blocked = client.delete(f"/api/v1/vendors/{vendor['id']}")
    assert blocked.status_code == 409

    # 无合同的单位可以删除
    other = _create_vendor(client, "另一家保洁公司")
    assert client.delete(f"/api/v1/vendors/{other['id']}").status_code == 200

    # 合同删除保护：有结算后不能删
    now = datetime.now()
    client.post(
        f"/api/v1/contracts/{contract['id']}/settlements",
        json={"period_year": now.year, "period_month": now.month, "assessor": "考核员"},
    )
    assert client.delete(f"/api/v1/contracts/{contract['id']}").status_code == 409


def test_contract_scope_conflict_and_dates(client, restroom):
    vendor = _create_vendor(client, "城东保洁公司")
    today = date.today()
    _create_contract(
        client, vendor["id"], [restroom["id"]],
        start=today.replace(day=1), end=date(today.year, 12, 31),
    )
    vendor2 = _create_vendor(client, "城西保洁公司")
    # 同一公厕同一时段重复覆盖被拒绝
    conflict = client.post(
        "/api/v1/contracts",
        json={
            "vendor_id": vendor2["id"],
            "name": "重复合同",
            "start_date": today.replace(day=1).isoformat(),
            "end_date": date(today.year, 12, 31).isoformat(),
            "monthly_fee": 8000,
            "restroom_ids": [restroom["id"]],
        },
    )
    assert conflict.status_code == 400
    assert "重叠" in conflict.json()["detail"]

    # 结束日期早于开始日期被拒绝
    bad_dates = client.post(
        "/api/v1/contracts",
        json={
            "vendor_id": vendor2["id"],
            "name": "日期错误合同",
            "start_date": date(today.year, 12, 31).isoformat(),
            "end_date": today.replace(day=1).isoformat(),
            "monthly_fee": 8000,
            "restroom_ids": [],
        },
    )
    assert bad_dates.status_code == 422

    # 公厕详情可以反查覆盖合同
    detail = client.get(f"/api/v1/restrooms/{restroom['id']}").json()
    assert len(detail["active_contracts"]) == 1
    assert detail["active_contracts"][0]["vendor_name"] == "城东保洁公司"


def test_settlement_score_deduction(client, restroom):
    vendor = _create_vendor(client, "优质保洁公司")
    contract = _create_contract(client, vendor["id"], [restroom["id"]], fee=10000.0)
    now = datetime.now()

    # 全部 8 分 → 百分制 80，落在 80-85 档，扣 2%
    client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "巡查员", "items": full_items(8)},
    )
    preview = client.get(
        f"/api/v1/contracts/{contract['id']}/assessment-preview",
        params={"year": now.year, "month": now.month},
    ).json()
    assert preview["avg_score"] == 80.0
    assert preview["score_deduction"] == 200.0
    assert preview["payable_amount"] == 9800.0

    created = client.post(
        f"/api/v1/contracts/{contract['id']}/settlements",
        json={"period_year": now.year, "period_month": now.month, "assessor": "考核员"},
    ).json()
    assert created["code"].startswith(f"JS-{now.year}{now.month:02d}-")
    assert created["score_deduction"] == 200.0
    assert created["payable_amount"] == 9800.0

    # 同一月份重复生成被拒绝
    duplicate = client.post(
        f"/api/v1/contracts/{contract['id']}/settlements",
        json={"period_year": now.year, "period_month": now.month},
    )
    assert duplicate.status_code == 400


def test_settlement_issue_deduction_and_trace(client, restroom):
    vendor = _create_vendor(client, "整改扣款保洁公司")
    contract = _create_contract(client, vendor["id"], [restroom["id"]], fee=10000.0)
    now = datetime.now()

    # 一次低质量巡查并上报严重问题，期限设在昨天 → 期末超期
    inspection = client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "巡查员", "items": full_items(4)},
    ).json()
    issue = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": restroom["id"],
            "inspection_id": inspection["id"],
            "title": "地面严重污渍",
            "category": "保洁不到位",
            "severity": "严重",
            "deadline": (now - timedelta(days=1)).isoformat(),
        },
    ).json()

    settlement = client.post(
        f"/api/v1/contracts/{contract['id']}/settlements",
        json={"period_year": now.year, "period_month": now.month, "assessor": "考核员"},
    ).json()
    # 均分 40 → 扣 10% = 1000；新上报严重问题 100；超期未闭环 300
    assert settlement["score_deduction"] == 1000.0
    assert settlement["issue_deduction"] == 100.0
    assert settlement["overdue_deduction"] == 300.0
    assert settlement["issue_new_count"] == 1
    assert settlement["issue_overdue_count"] == 1
    assert settlement["payable_amount"] == 8600.0
    assert settlement["assess_grade"] == "不合格"

    # 依据明细可回溯到问题工单
    detail = client.get(f"/api/v1/settlements/{settlement['id']}").json()
    ref_ids = {e["ref_id"] for e in detail["evidences"] if e["ref_type"] == "issue"}
    assert issue["id"] in ref_ids

    # 反向追溯：问题 → 结算单
    traced = client.get(f"/api/v1/issues/{issue['id']}/settlements").json()
    assert len(traced) == 1
    assert traced[0]["settlement_id"] == settlement["id"]
    assert traced[0]["vendor_name"] == "整改扣款保洁公司"


def test_settlement_reject_deduction_and_cap(client, restroom):
    vendor = _create_vendor(client, "驳回测试保洁公司")
    contract = _create_contract(client, vendor["id"], [restroom["id"]], fee=1000.0)
    now = datetime.now()

    inspection = client.post(
        "/api/v1/inspections",
        json={"restroom_id": restroom["id"], "inspector": "巡查员", "items": full_items(4)},
    ).json()
    issue = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": restroom["id"],
            "inspection_id": inspection["id"],
            "title": "耗材缺失",
            "category": "耗材缺失",
            "severity": "一般",
            "deadline": (now + timedelta(days=3)).isoformat(),
        },
    ).json()
    # 整改 → 验收 → 驳回，产生一次 150 元驳回扣款
    for target in ("整改中", "待验收", "整改中"):
        resp = client.post(
            f"/api/v1/issues/{issue['id']}/transitions",
            json={"to_status": target, "operator": "值班长"},
        )
        assert resp.status_code == 200, resp.text

    settlement = client.post(
        f"/api/v1/contracts/{contract['id']}/settlements",
        json={"period_year": now.year, "period_month": now.month},
    ).json()
    assert settlement["issue_reject_count"] == 1
    assert settlement["reject_deduction"] == 150.0
    # 月费 1000：质量扣款 100、新问题 50、驳回 150 合计 300，
    # 超过月费 30% 封顶 300，恰好持平
    assert settlement["total_deduction"] == 300.0
    assert settlement["payable_amount"] == 700.0


def test_settlement_adjust_confirm_and_guard(client, restroom):
    vendor = _create_vendor(client, "结算流程保洁公司")
    contract = _create_contract(client, vendor["id"], [restroom["id"]], fee=10000.0)
    now = datetime.now()
    settlement = client.post(
        f"/api/v1/contracts/{contract['id']}/settlements",
        json={"period_year": now.year, "period_month": now.month, "assessor": "考核员"},
    ).json()

    # 手工登记其他扣款与奖励
    adjusted = client.patch(
        f"/api/v1/settlements/{settlement['id']}",
        json={"other_deduction": 500, "other_reason": "群众投诉扣罚", "bonus": 200},
    ).json()
    assert adjusted["other_deduction"] == 500.0
    assert adjusted["bonus"] == 200.0
    assert adjusted["payable_amount"] == 9700.0

    # 已结算后不能再调整/重新考核
    confirmed = client.post(
        f"/api/v1/settlements/{settlement['id']}/confirm",
        json={"operator": "财务科", "remark": "已支付"},
    ).json()
    assert confirmed["status"] == "已结算"
    assert confirmed["settle_operator"] == "财务科"
    assert client.post(
        f"/api/v1/settlements/{settlement['id']}/reassess"
    ).status_code == 400
    assert client.patch(
        f"/api/v1/settlements/{settlement['id']}", json={"bonus": 1}
    ).status_code == 400
    assert client.delete(f"/api/v1/settlements/{settlement['id']}").status_code == 400

    # 结算台账可以按单位与状态过滤
    listed = client.get(
        "/api/v1/settlements",
        params={"vendor_id": vendor["id"], "status": "已结算"},
    ).json()
    assert listed["meta"]["total"] == 1


def test_settlement_period_outside_contract_rejected(client, restroom):
    vendor = _create_vendor(client, "期限测试保洁公司")
    contract = _create_contract(
        client, vendor["id"], [restroom["id"]],
        start=date(date.today().year, 3, 1), end=date(date.today().year, 6, 30),
    )
    rejected = client.post(
        f"/api/v1/contracts/{contract['id']}/settlements",
        json={"period_year": date.today().year, "period_month": 1},
    )
    assert rejected.status_code == 400
    assert "合同期限" in rejected.json()["detail"]


def test_force_delete_restroom_keeps_contract_clean(client):
    """公厕被强制删除后，合同保留但服务范围关联被清理，无悬空数据。"""
    room = client.post(
        "/api/v1/restrooms",
        json={"name": "级联测试公厕", "district": "测试区", "address": "测试路 8 号"},
    ).json()
    vendor = _create_vendor(client, "级联测试保洁公司")
    contract = _create_contract(client, vendor["id"], [room["id"]])

    response = client.delete(f"/api/v1/restrooms/{room['id']}", params={"force": "true"})
    assert response.status_code == 200

    detail = client.get(f"/api/v1/contracts/{contract['id']}").json()
    assert detail["restroom_count"] == 0
    assert client.get("/api/v1/contracts").status_code == 200
