import pytest
from pydantic import ValidationError

from kdm.schema import (
    DecisionOption,
    KDMap,
    Stage,
)
from tests.conftest import sample_map


def test_sample_map_valid():
    m = sample_map()
    assert m.mode == "build"
    assert len(m.stages) == 3
    assert len(m.nodes) == 4


def test_stage_count_bounds():
    base = sample_map().model_dump()
    base["stages"] = [Stage(id="s1", title="A", order=1).model_dump()]
    with pytest.raises(ValidationError, match="3–5"):
        KDMap.model_validate(base)


def test_duplicate_node_id():
    base = sample_map().model_dump()
    base["nodes"].append(base["nodes"][0])
    with pytest.raises(ValidationError, match="unique"):
        KDMap.model_validate(base)


def test_invalid_depends_on():
    base = sample_map().model_dump()
    base["nodes"][1]["depends_on"] = ["ghost"]
    with pytest.raises(ValidationError, match="not found"):
        KDMap.model_validate(base)


def test_decision_requires_fields():
    base = sample_map().model_dump()
    base["nodes"][1]["options"] = [
        DecisionOption(name="A", pros=[], cons=[], fit_reason="ok").model_dump()
    ]
    with pytest.raises(ValidationError, match="2–3 options"):
        KDMap.model_validate(base)


def test_checkpoint_requires_proof():
    base = sample_map().model_dump()
    base["nodes"][2]["proof"] = None
    with pytest.raises(ValidationError, match="proof"):
        KDMap.model_validate(base)


def test_disclaimer_required_for_external_validation():
    base = sample_map().model_dump()
    base["nodes"][2]["requires_external_validation"] = True
    base["disclaimer"] = None
    with pytest.raises(ValidationError, match="disclaimer"):
        KDMap.model_validate(base)
