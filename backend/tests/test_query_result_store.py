"""publish_query_result — the wire frame the chat bubble keys on."""
from unittest.mock import MagicMock

from backend.services.query_result_store import publish_query_result


def test_wire_frame_carries_the_turn_id_and_no_sql(monkeypatch):
    publish = MagicMock()
    monkeypatch.setattr(
        "backend.services.ws_connection_manager.ConnectionManager.publish_to_user_sync",
        publish,
    )

    publish_query_result("u-1", "ref-1", {"sql": "SELECT 1", "rows": [[1]]}, request_id="req-1")

    user_id, frame = publish.call_args.args
    assert user_id == "u-1"
    assert frame == {
        "type": "query.result",
        "request_id": "req-1",
        "result_ref": "ref-1",
        "data": {"rows": [[1]]},
    }
