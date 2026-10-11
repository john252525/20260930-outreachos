"""Unit tests for the deterministic variant assigner."""

from experiments_service.engine.variant_assigner import VariantAssigner


def test_deterministic() -> None:
    a = VariantAssigner()
    variants = [{"id": "A", "weight": 0.5}, {"id": "B", "weight": 0.5}]
    v1 = a.assign(experiment_id="exp1", contact_id="c1", variants=variants)
    v2 = a.assign(experiment_id="exp1", contact_id="c1", variants=variants)
    assert v1 == v2
    assert v1 in ("A", "B")


def test_distribution_balanced() -> None:
    a = VariantAssigner()
    variants = [{"id": "A", "weight": 0.5}, {"id": "B", "weight": 0.5}]
    counts = {"A": 0, "B": 0}
    for i in range(1000):
        v = a.assign(experiment_id="exp1", contact_id=f"c{i}", variants=variants)
        assert v is not None
        counts[v] += 1
    assert 400 < counts["A"] < 600
    assert 400 < counts["B"] < 600


def test_empty_variants_returns_none() -> None:
    a = VariantAssigner()
    assert a.assign(experiment_id="e", contact_id="c", variants=[]) is None


def test_weighted_skew() -> None:
    a = VariantAssigner()
    variants = [{"id": "A", "weight": 0.9}, {"id": "B", "weight": 0.1}]
    counts = {"A": 0, "B": 0}
    for i in range(2000):
        v = a.assign(experiment_id="e2", contact_id=f"x{i}", variants=variants)
        assert v is not None
        counts[v] += 1
    assert counts["A"] > counts["B"]
