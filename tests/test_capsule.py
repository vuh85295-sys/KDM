from kdm.capsule import ApprovedDecision, export_capsule, slugify
from kdm.schema import NodeType
from tests.conftest import sample_map


def test_slugify():
    assert slugify("Ứng dụng bãi đỗ", "Realtime slot")


def test_export_capsule():
    m = sample_map()
    approved = [
        ApprovedDecision(
            node_id="db_choice",
            chosen_option="SQLite",
            reason="MVP đủ dùng",
        )
    ]
    cap = export_capsule(m, approved)
    assert cap.topic
    assert "anti-map" in cap.global_context.lower() or "Ngoài phạm vi" in cap.global_context
    assert any("SQLite" in d for d in cap.key_decisions)
    assert "Stage hiện tại" in cap.current_state


def test_export_includes_disclaimer():
    m = sample_map()
    m.disclaimer = "Cần KTS thẩm địn"
    m.nodes[2].requires_external_validation = True
    cap = export_capsule(m, [])
    assert "Disclaimer" in cap.global_context
