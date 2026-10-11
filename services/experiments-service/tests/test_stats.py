"""Unit tests for the statistics engine."""

from experiments_service.engine.stats_engine import StatsEngine


def test_significant_winner() -> None:
    engine = StatsEngine()
    result = engine.compute(
        variants_data=[
            {"variant_id": "A", "sent": 500, "positive_replied": 50, "replied": 100},
            {"variant_id": "B", "sent": 500, "positive_replied": 20, "replied": 40},
        ],
        primary_metric="positive_reply_rate",
        sample_size_per_variant=100,
        minimum_detectable_effect=0.01,
    )
    assert result.is_significant
    assert result.winner_variant_id == "A"


def test_not_significant() -> None:
    engine = StatsEngine()
    result = engine.compute(
        variants_data=[
            {"variant_id": "A", "sent": 500, "positive_replied": 30, "replied": 60},
            {"variant_id": "B", "sent": 500, "positive_replied": 28, "replied": 58},
        ],
        primary_metric="positive_reply_rate",
        sample_size_per_variant=100,
        minimum_detectable_effect=0.01,
    )
    assert not result.is_significant


def test_insufficient_data() -> None:
    engine = StatsEngine()
    result = engine.compute(
        variants_data=[
            {"variant_id": "A", "sent": 10, "positive_replied": 1, "replied": 2},
            {"variant_id": "B", "sent": 10, "positive_replied": 0, "replied": 1},
        ],
        primary_metric="positive_reply_rate",
        sample_size_per_variant=100,
        minimum_detectable_effect=0.01,
    )
    assert not result.is_significant
    assert "Недостаточно" in result.reason


def test_mde_blocks_winner() -> None:
    engine = StatsEngine()
    # Huge samples, tiny absolute difference -> significant but below MDE.
    result = engine.compute(
        variants_data=[
            {"variant_id": "A", "sent": 100000, "positive_replied": 50000, "replied": 50000},
            {"variant_id": "B", "sent": 100000, "positive_replied": 49500, "replied": 49500},
        ],
        primary_metric="positive_reply_rate",
        sample_size_per_variant=100,
        minimum_detectable_effect=1.0,
    )
    assert not result.is_significant
    assert result.winner_variant_id is None


def test_empty_variants() -> None:
    engine = StatsEngine()
    result = engine.compute(
        variants_data=[],
        primary_metric="positive_reply_rate",
        sample_size_per_variant=100,
        minimum_detectable_effect=0.01,
    )
    assert not result.is_significant
    assert result.variants == []


def test_reply_rate_metric() -> None:
    engine = StatsEngine()
    result = engine.compute(
        variants_data=[
            {"variant_id": "A", "sent": 300, "replied": 60},
            {"variant_id": "B", "sent": 300, "replied": 12},
        ],
        primary_metric="reply_rate",
        sample_size_per_variant=100,
        minimum_detectable_effect=0.01,
    )
    assert result.is_significant
    assert result.winner_variant_id == "A"
