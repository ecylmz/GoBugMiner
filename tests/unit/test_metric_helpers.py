from gobugminer.metrics.extract import sum_or_none


def test_sum_or_none_with_all_values_present() -> None:
    assert sum_or_none([1, 2, 3]) == 6


def test_sum_or_none_ignores_unavailable_components() -> None:
    assert sum_or_none([1, None, 3]) == 4


def test_sum_or_none_preserves_all_unavailable_as_null() -> None:
    assert sum_or_none([None, None]) is None


def test_sum_or_none_empty_measurement_set_is_null() -> None:
    assert sum_or_none([]) is None


def test_sum_or_none_supports_mixed_numeric_measurements() -> None:
    assert sum_or_none([1, 2.5, None]) == 3.5


def test_legitimate_empty_entity_count_remains_zero() -> None:
    assert sum(len(methods) for methods in []) == 0
