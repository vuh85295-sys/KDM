from kdm.capsule import ApprovedDecision, export_capsule, make_topic_slug, slugify
from kdm.schema import NodeType
from tests.conftest import sample_map


def test_slugify():
    assert slugify("Ứng dụng bãi đỗ", "Realtime slot") == "ung-dung-bai-do-realtime-slot"


def test_make_topic_slug_short_unchanged():
    slug = make_topic_slug("Parking", "realtime")
    assert slug == "parking-realtime"
    assert slug == slug.strip("-")
    assert slug.isascii()


def test_make_topic_slug_long_vietnamese():
    domain = "Ứng dụng tìm chỗ đậu xe thông minh"
    target = (
        "Cho phép tài xế và chủ bãi xem slot trống realtime theo geohash "
        "với độ trễ dưới ba giây tại thành phố Hồ Chí Minh và vùng lân cận"
    )
    assert len(f"{domain} {target}") > 150

    slug = make_topic_slug(domain, target)

    assert len(slug) <= 50
    assert slug.isascii()
    assert not slug.startswith("-")
    assert not slug.endswith("-")
    assert "ung-dung" in slug
    assert "đ" not in slug


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
