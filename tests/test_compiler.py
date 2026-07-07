from kdm.compiler import kdm_to_mermaid, sanitize_label
from tests.conftest import sample_map


def test_sanitize_special_chars():
    raw = 'API "test" & (gateway) [v1]'
    out = sanitize_label(raw)
    assert '"' not in out
    assert "(" not in out
    assert "[" not in out
    assert "&amp;" in out


def test_mermaid_contains_nodes():
    m = sample_map()
    md = kdm_to_mermaid(m)
    assert "flowchart TD" in md
    assert "db_choice" in md
    assert "owner" in md
    assert "owner --> db_choice" in md


def test_decision_emoji_and_class():
    m = sample_map()
    md = kdm_to_mermaid(m)
    assert "🟡" in md
    assert "class db_choice revYellow" in md


def test_subgraph_per_stage():
    m = sample_map()
    md = kdm_to_mermaid(m)
    assert 'subgraph s1["MVP cảm biến"]' in md
    assert 'subgraph s2["App mobile"]' in md


def test_label_special_node():
    m = sample_map()
    md = kdm_to_mermaid(m)
    assert "label_special" in md
    assert "#quot;" in md or "API" in md
