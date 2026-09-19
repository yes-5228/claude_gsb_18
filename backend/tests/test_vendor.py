"""保洁外包：单位、合同、月度考核扣款与双向追溯测试。"""

from datetime import date, datetime, timedelta

from tests.conftest import full_items

DISTRICT = "考核测试区"


def _create_restroom(client, name="考核公厕", district=DISTRICT):
    return client.post(
        "/api/v1/restrooms",
        json={"name": name, "district": district, "address": "考核路 1 号"},
    ).json()


def _create_vendor(client, name="考核保洁服务有限公司"):
    return client.post(
        "/api/v1/vendors",
        json={
            "name": name,
            "license_no": "91330100TEST00001X",
            "contact_person": "考核联系人",
            "contact_phone": "13800000000",
        },
    ).json()


def _create_contract(client, vendor_id, district=DISTRICT, monthly_fee=10000.0):
    today = date.today()
    return client.post(
        "/api/v1/contracts",
        json={
            "vendor_id": vendor_id,
            "name": "考核测试外包合同",
            "scope_type": "按区域",
            "scope_districts": [district],
            "scope_restroom_ids": [],
            "start_date": today.replace(day=1).isoformat(),
            "end_date": (today.replace(day=28) + timedelta(days=300)).isoformat(),
            "monthly_fee": monthly_fee,
        },
    ).json()


def test_vendor_crud_and_delete_guard(client):
    payload = client.post(
        "/api/v1/vendors",
        json={"name": "删除保护测试公司", "contact_person": "张三"},
    )
    vendor = payload.json()
    assert vendor["code"].startswith("WB-")
    assert vendor["status"] == "合作中"

    listed = client.get("/api/v1/vendors", params={"keyword": "删除保护"}).json()
    assert listed["meta"]["total"] >= 1

    changed = client.patch(
        f"/api/v1/vendors/{vendor['id']}", json={"status": "暂停合作"}
    ).json()
    assert changed["status"] == "暂停合作"

    contract = _create_contract(client, vendor["id"])
    assert contract["scope_restroom_count"] == 0  # 新区域内暂无公厕

    blocked = client.delete(f"/api/v1/vendors/{vendor['id']}")
    assert blocked.status_code == 409

    detail = client.get(f"/api/v1/vendors/{vendor['id']}").json()
    assert detail["contract_count"] == 1


def test_contract_validation_and_scope(client):
    district = "范围校验区"
    vendor = _create_vendor(client, "范围校验保洁公司")
    restroom = _create_restroom(client, "指定范围公厕", district)
    today = date.today()

    # 结束日期早于开始日期
    bad_date = client.post(
        "/api/v1/contracts",
        json={
            "vendor_id": vendor["id"],
            "name": "期限错误合同",
            "scope_type": "按区域",
            "scope_districts": [district],
            "start_date": today.isoformat(),
            "end_date": (today - timedelta(days=1)).isoformat(),
            "monthly_fee": 1000,
        },
    )
    assert bad_date.status_code == 400

    # 按区域但未选区域
    empty_scope = client.post(
        "/api/v1/contracts",
        json={
            "vendor_id": vendor["id"],
            "name": "空范围合同",
            "scope_type": "按区域",
            "scope_districts": [],
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "monthly_fee": 1000,
        },
    )
    assert empty_scope.status_code == 400

    # 指定公厕引用不存在的 ID
    bad_ref = client.post(
        "/api/v1/contracts",
        json={
            "vendor_id": vendor["id"],
            "name": "错误公厕合同",
            "scope_type": "指定公厕",
            "scope_restroom_ids": [999999],
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=30)).isoformat(),
            "monthly_fee": 1000,
        },
    )
    assert bad_ref.status_code == 400

    ok = client.post(
        "/api/v1/contracts",
        json={
            "vendor_id": vendor["id"],
            "name": "指定公厕合同",
            "scope_type": "指定公厕",
            "scope_restroom_ids": [restroom["id"]],
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=365)).isoformat(),
            "monthly_fee": 8800,
        },
    )
    assert ok.status_code == 201, ok.text
    body = ok.json()
    assert body["scope_restroom_count"] == 1
    assert "指定 1 座公厕" in body["scope_text"]


def test_settlement_assessment_deduction_and_trace(client):
    vendor = _create_vendor(client, "扣款计算保洁公司")
    restroom = _create_restroom(client, "扣款计算公厕", "扣款计算区")
    contract = _create_contract(client, vendor["id"], district="扣款计算区", monthly_fee=10000.0)
    period = date.today().strftime("%Y-%m")

    # 一条低分巡查：全部 4 分 → 40 分 → 月费 8% 质量扣款 = 800
    inspection = client.post(
        "/api/v1/inspections",
        json={
            "restroom_id": restroom["id"],
            "inspector": "考核巡查员",
            "items": full_items(4),
        },
    ).json()
    assert inspection["score"] == 40.0

    # 一条紧急且已超期未闭环的问题：300（紧急问题）+ 200（超期）= 500
    issue = client.post(
        "/api/v1/issues",
        json={
            "restroom_id": restroom["id"],
            "title": "考核用超期问题",
            "category": "安全隐患",
            "severity": "紧急",
            "deadline": (datetime.now() - timedelta(days=2)).isoformat(),
        },
    ).json()

    preview = client.get(
        "/api/v1/settlements/preview",
        params={"contract_id": contract["id"], "period_month": period},
    ).json()
    assert preview["quality_deduction"] == 800.0
    assert preview["issue_count"] == 1
    assert preview["overdue_count"] == 1
    assert preview["total_deduction"] == 1300.0
    assert preview["payable_amount"] == 8700.0

    # 合同期限外的月份不允许建单
    invalid_month = client.post(
        "/api/v1/settlements",
        json={"contract_id": contract["id"], "period_month": "2000-01"},
    )
    assert invalid_month.status_code == 400

    created = client.post(
        "/api/v1/settlements",
        json={"contract_id": contract["id"], "period_month": period},
    ).json()
    assert created["status"] == "待考核"

    # 重复登记被拒绝
    duplicate = client.post(
        "/api/v1/settlements",
        json={"contract_id": contract["id"], "period_month": period},
    )
    assert duplicate.status_code == 400

    # 待考核状态不能直接结算
    invalid_flow = client.post(
        f"/api/v1/settlements/{created['id']}/transitions",
        json={"to_status": "已结算", "operator": "财务"},
    )
    assert invalid_flow.status_code == 400

    assessed = client.post(
        f"/api/v1/settlements/{created['id']}/assess",
        json={"to_status": "已考核", "operator": "考核员"},
    ).json()
    assert assessed["status"] == "已考核"
    assert assessed["quality_deduction"] == 800.0
    assert assessed["issue_deduction"] == 300.0
    assert assessed["overdue_deduction"] == 200.0
    assert assessed["payable_amount"] == 8700.0
    assert len(assessed["details"]) >= 3

    detail = client.get(f"/api/v1/settlements/{created['id']}").json()
    assert {link["inspection_id"] for link in detail["inspection_links"]} == {inspection["id"]}
    issue_link = detail["issue_links"][0]
    assert issue_link["issue_id"] == issue["id"]
    assert issue_link["is_overdue"] is True
    assert issue_link["deduction"] == 500.0

    # 双向追溯：巡查/问题 → 结算单
    inspection_trace = client.get(
        f"/api/v1/settlements/trace/inspection/{inspection['id']}"
    ).json()
    assert len(inspection_trace) == 1
    assert inspection_trace[0]["settlement_id"] == created["id"]
    assert inspection_trace[0]["vendor_name"] == "扣款计算保洁公司"

    issue_trace = client.get(f"/api/v1/settlements/trace/issue/{issue['id']}").json()
    assert issue_trace[0]["deduction"] == 500.0

    # 其他扣款调整 +100：应扣 1400，应付 8600
    adjusted = client.post(
        f"/api/v1/settlements/{created['id']}/manual",
        json={"manual_deduction": 100, "manual_reason": "暗访发现问题，追加扣款"},
    ).json()
    assert adjusted["total_deduction"] == 1400.0
    assert adjusted["payable_amount"] == 8600.0

    # 确认结算后金额锁定，不能再调整或删除
    settled = client.post(
        f"/api/v1/settlements/{created['id']}/transitions",
        json={"to_status": "已结算", "operator": "财务科", "remark": "已付款"},
    ).json()
    assert settled["status"] == "已结算"
    assert settled["settled_by"] == "财务科"

    locked = client.post(
        f"/api/v1/settlements/{created['id']}/manual",
        json={"manual_deduction": 50, "manual_reason": "试图修改"},
    )
    assert locked.status_code == 400
    assert client.delete(f"/api/v1/settlements/{created['id']}").status_code == 400

    # 撤销结算后恢复可编辑
    revoked = client.post(
        f"/api/v1/settlements/{created['id']}/transitions",
        json={"to_status": "已考核", "operator": "财务科"},
    )
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "已考核"

    # 退回重做：扣款与明细清空，重新回到待考核
    reset = client.post(
        f"/api/v1/settlements/{created['id']}/transitions",
        json={"to_status": "待考核", "operator": "考核员", "remark": "数据有误，重新考核"},
    )
    assert reset.status_code == 200
    reset_body = reset.json()
    assert reset_body["status"] == "待考核"
    assert reset_body["total_deduction"] == 0.0
    assert reset_body["payable_amount"] == 0.0
    assert reset_body["avg_score"] is None
    detail_after_reset = client.get(f"/api/v1/settlements/{created['id']}").json()
    assert detail_after_reset["details"] == []
    assert detail_after_reset["issue_links"] == []
    assert detail_after_reset["inspection_links"] == []


def test_contract_covering_restroom(client):
    vendor = _create_vendor(client, "覆盖关系保洁公司")
    restroom = _create_restroom(client, "覆盖关系公厕", "覆盖关系区")
    today = date.today()
    contract = client.post(
        "/api/v1/contracts",
        json={
            "vendor_id": vendor["id"],
            "name": "覆盖关系合同",
            "scope_type": "按区域",
            "scope_districts": ["覆盖关系区"],
            "start_date": today.isoformat(),
            "end_date": (today + timedelta(days=300)).isoformat(),
            "monthly_fee": 9000,
        },
    ).json()

    rows = client.get(f"/api/v1/contracts/covering/{restroom['id']}").json()
    assert any(row["id"] == contract["id"] for row in rows)
    assert client.get("/api/v1/contracts/covering/999999").status_code == 404


def test_good_service_has_no_quality_deduction(client):
    vendor = _create_vendor(client, "优质服务保洁公司")
    restroom = _create_restroom(client, "优质服务公厕", "优质服务区")
    contract = _create_contract(client, vendor["id"], district="优质服务区", monthly_fee=20000.0)
    period = date.today().strftime("%Y-%m")

    # 两条满分巡查，无问题
    for _ in range(2):
        client.post(
            "/api/v1/inspections",
            json={"restroom_id": restroom["id"], "inspector": "督查", "items": full_items(10)},
        )

    created = client.post(
        "/api/v1/settlements",
        json={"contract_id": contract["id"], "period_month": period},
    ).json()
    assessed = client.post(
        f"/api/v1/settlements/{created['id']}/assess",
        json={"to_status": "已考核", "operator": "考核员"},
    ).json()
    assert assessed["avg_score"] == 100.0
    assert assessed["quality_deduction"] == 0.0
    assert assessed["issue_deduction"] == 0.0
    assert assessed["payable_amount"] == 20000.0
    assert assessed["details"] == []


def test_contract_detail_contains_settlement_ledger(client):
    vendor = _create_vendor(client, "台账查询保洁公司")
    _create_restroom(client, "台账查询公厕")
    contract = _create_contract(client, vendor["id"], monthly_fee=12000.0)
    period = date.today().strftime("%Y-%m")

    created = client.post(
        "/api/v1/settlements",
        json={"contract_id": contract["id"], "period_month": period},
    ).json()
    client.post(
        f"/api/v1/settlements/{created['id']}/assess",
        json={"to_status": "已考核", "operator": "考核员"},
    )

    detail = client.get(f"/api/v1/contracts/{contract['id']}").json()
    assert detail["settlement_count"] == 1
    assert detail["latest_period"] == period
    assert detail["settlements"][0]["code"] == created["code"]
    assert detail["vendor"] is not None
