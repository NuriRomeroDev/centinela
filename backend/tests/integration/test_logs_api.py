"""Logs API integration tests (T2.6, RED).

Scenarios (logs-api spec R1–R4, tasks.md T2.6):
- keyset pagination: first page, cursor walk (every row once, no gaps/overlap)
- offset paging (page/page_size) + page_size clamp (1–100)
- search: single-field ILIKE contains, case-insensitive, filtered total
- composed filters (AND): codigo_error + servicio_responsable
- detail endpoint: full row incl. stack_trace; 404 unknown id
- empty result shape: items=[], total=0, next_cursor=null
"""

import math

from tests.integration.helpers import log_row, sync_row

LOGS_URL = "/api/v1/logs"


async def _seed_logs(db_session, count: int) -> None:
    sync = sync_row()
    db_session.add(sync)
    await db_session.flush()
    db_session.add_all(
        [
            log_row(
                sync,
                codigo=f"ERR_{i:02d}",
                mensaje=f"mensaje {i}",
                servicio="Validation_Engine" if i % 2 else "DB_Connection_Pool",
            )
            for i in range(count)
        ]
    )
    await db_session.commit()


async def test_logs_first_page_shape_and_total(api_client, db_session):
    await _seed_logs(db_session, 38)

    response = await api_client.get(LOGS_URL, params={"page_size": 9})
    assert response.status_code == 200
    body = response.json()

    assert len(body["items"]) == 9
    assert body["total"] == 38
    assert body["page_size"] == 9
    assert body["next_cursor"] is not None
    assert [item["id"] for item in body["items"]] == list(range(38, 29, -1))  # newest first
    assert math.ceil(38 / 9) == 5  # footer page squares derivable client-side
    assert set(body["items"][0].keys()) == {
        "id",
        "correlation_id",
        "nivel_error",
        "codigo_error",
        "mensaje",
        "servicio_responsable",
        "creado_at",
    }


async def test_logs_cursor_walk_returns_every_row_once(api_client, db_session):
    await _seed_logs(db_session, 38)

    cursor = None
    seen: list[int] = []
    while True:
        params = {"page_size": 9}
        if cursor is not None:
            params["cursor"] = cursor
        body = (await api_client.get(LOGS_URL, params=params)).json()
        seen.extend(item["id"] for item in body["items"])
        if body["next_cursor"] is None:
            break
        cursor = body["next_cursor"]

    assert seen == list(range(38, 0, -1))  # every row exactly once, newest→oldest


async def test_logs_offset_paging_returns_correct_slice(api_client, db_session):
    await _seed_logs(db_session, 38)

    page1 = (await api_client.get(LOGS_URL, params={"page": 1, "page_size": 10})).json()
    page2 = (await api_client.get(LOGS_URL, params={"page": 2, "page_size": 10})).json()

    assert [item["id"] for item in page1["items"]] == list(range(38, 28, -1))
    assert [item["id"] for item in page2["items"]] == list(range(28, 18, -1))
    assert page2["total"] == 38
    assert page2["page"] == 2
    assert page2["next_cursor"] == 19  # more rows exist below id 19


async def test_logs_page_size_is_clamped_to_1_and_100(api_client, db_session):
    await _seed_logs(db_session, 105)

    huge = (await api_client.get(LOGS_URL, params={"page_size": 999})).json()
    assert len(huge["items"]) == 100  # clamped to max 100
    assert huge["page_size"] == 100

    tiny = (await api_client.get(LOGS_URL, params={"page_size": 0})).json()
    assert len(tiny["items"]) == 1  # clamped up to 1
    assert tiny["page_size"] == 1


async def test_logs_search_is_case_insensitive_contains_with_filtered_total(api_client, db_session):
    await _seed_logs(db_session, 38)

    response = await api_client.get(LOGS_URL, params={"search": "err_05"})  # lowercase
    body = response.json()
    assert body["total"] == 1
    assert [item["codigo_error"] for item in body["items"]] == ["ERR_05"]

    response = await api_client.get(LOGS_URL, params={"search": "mensaje 3"})
    body = response.json()
    # matches "mensaje 3", "mensaje 30".."mensaje 37"
    assert body["total"] == 9
    assert all("mensaje 3" in item["mensaje"] for item in body["items"])


async def test_logs_filters_compose_with_and(api_client, db_session):
    await _seed_logs(db_session, 38)

    response = await api_client.get(
        LOGS_URL, params={"codigo_error": "ERR_", "servicio_responsable": "Validation_Engine"}
    )
    body = response.json()
    # 19 odd-indexed rows (i % 2 → Validation_Engine), all codigos contain ERR_
    assert body["total"] == 19
    assert all(item["servicio_responsable"] == "Validation_Engine" for item in body["items"])


async def test_logs_search_composes_with_cursor(api_client, db_session):
    await _seed_logs(db_session, 38)

    page1 = (await api_client.get(LOGS_URL, params={"search": "mensaje 2", "page_size": 5})).json()
    assert page1["total"] == 11  # mensaje 2, 20..29
    page2 = (
        await api_client.get(
            LOGS_URL, params={"search": "mensaje 2", "page_size": 5, "cursor": page1["next_cursor"]}
        )
    ).json()

    seen = [item["id"] for item in page1["items"]] + [item["id"] for item in page2["items"]]
    assert len(seen) == len(set(seen))  # no overlap
    assert len(page2["items"]) == 5
    assert page2["next_cursor"] is not None
    page3 = (
        await api_client.get(
            LOGS_URL, params={"search": "mensaje 2", "page_size": 5, "cursor": page2["next_cursor"]}
        )
    ).json()
    assert len(page3["items"]) == 1  # 11 = 5 + 5 + 1
    assert page3["next_cursor"] is None


async def test_logs_detail_returns_full_row_with_stack_trace(api_client, db_session):
    sync = sync_row()
    db_session.add(sync)
    await db_session.flush()
    log = log_row(sync, codigo="ERR_JSON_MALFORMED", stack="Traceback (most recent call last): ...")
    db_session.add(log)
    await db_session.commit()

    response = await api_client.get(f"{LOGS_URL}/{log.id}")
    assert response.status_code == 200
    body = response.json()
    assert body["id"] == log.id
    assert body["codigo_error"] == "ERR_JSON_MALFORMED"
    assert body["stack_trace"] == "Traceback (most recent call last): ..."
    assert body["correlation_id"] == str(sync.correlation_id)


async def test_logs_detail_returns_404_for_unknown_id(api_client, db_session):
    await _seed_logs(db_session, 3)

    response = await api_client.get(f"{LOGS_URL}/999999")
    assert response.status_code == 404
    assert response.json()["error"]["codigo"] == "ERR_NOT_FOUND"


async def test_logs_empty_result_shape(api_client, db_session):
    await _seed_logs(db_session, 5)

    response = await api_client.get(LOGS_URL, params={"search": "zzz_none"})
    assert response.status_code == 200
    assert response.json() == {
        "items": [],
        "total": 0,
        "next_cursor": None,
        "page_size": 25,
        "page": 1,
    }
