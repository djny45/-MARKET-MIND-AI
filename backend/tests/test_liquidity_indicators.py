import pytest

from app.liquidity_indicators import calculate_volume_profile


def test_volume_profile_returns_poc_and_value_area():
    report = calculate_volume_profile(
        high=[10, 11, 12, 13], low=[8, 9, 10, 11],
        close=[9, 10, 11, 12], volume=[10, 30, 50, 10],
        bins=4, value_area_pct=70,
    )
    assert len(report["profile"]) == 4
    assert report["poc"] is not None
    assert report["value_area_high"] >= report["value_area_low"]
    assert report["total_volume"] == 100
    assert report["metadata"]["classification"].startswith("ohlcv_approximation")


def test_flat_price_profile_is_supported():
    report = calculate_volume_profile(
        high=[10, 10], low=[10, 10], close=[10, 10], volume=[2, 3]
    )
    assert len(report["profile"]) == 1
    assert report["total_volume"] == 5
    assert report["poc"] == 10


@pytest.mark.parametrize("kwargs", [
    {"bins": 1}, {"bins": 501}, {"value_area_pct": 0}, {"value_area_pct": 101},
])
def test_profile_rejects_invalid_parameters(kwargs):
    args = dict(high=[10, 11], low=[9, 10], close=[9.5, 10.5], volume=[1, 2])
    args.update(kwargs)
    with pytest.raises(ValueError):
        calculate_volume_profile(**args)


def test_profile_rejects_bad_ohlcv():
    with pytest.raises(ValueError):
        calculate_volume_profile(
            high=[8, 9], low=[9, 8], close=[8, 8.5], volume=[1, 2]
        )
