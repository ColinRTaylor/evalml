import numpy as np
import pandas as pd
import pytest

from evalml.pipelines.components import Undersampler


def test_init():
    parameters = {
        "sampling_ratio": 1,
        "min_samples": 1,
        "min_percentage": 0.5,
        "sampling_ratio_dict": None
    }
    undersampler = Undersampler(**parameters)
    assert undersampler.parameters == parameters


def test_none_y():
    X = pd.DataFrame([[i] for i in range(5)])
    undersampler = Undersampler()
    with pytest.raises(ValueError, match="y cannot be none"):
        undersampler.fit(X, None)
    with pytest.raises(ValueError, match="y cannot be none"):
        undersampler.fit_transform(X, None)
    undersampler.fit(X, pd.Series([0] * 4 + [1]))
    undersampler.transform(X, None)


@pytest.mark.parametrize("data_type", ["np", "pd", "ww"])
def test_no_undersample(data_type, make_data_type, X_y_binary):
    X, y = X_y_binary
    X = make_data_type(data_type, X)
    y = make_data_type(data_type, y)

    undersampler = Undersampler()
    new_X, new_y = undersampler.fit_transform(X, y)

    if data_type == "ww":
        X = X.to_dataframe().values
        y = y.to_series().values
    elif data_type == "pd":
        X = X.values
        y = y.values

    np.testing.assert_equal(X, new_X.to_dataframe().values)
    np.testing.assert_equal(y, new_y.to_series().values)


@pytest.mark.parametrize("data_type", ["np", "pd", "ww"])
def test_undersample_imbalanced(data_type, make_data_type):
    X = np.array([[i] for i in range(1000)])
    y = np.array([0] * 150 + [1] * 850)
    X = make_data_type(data_type, X)
    y = make_data_type(data_type, y)

    sampling_ratio = 0.25
    undersampler = Undersampler(sampling_ratio=sampling_ratio)
    new_X, new_y = undersampler.fit_transform(X, y)

    assert len(new_X) == 750
    assert len(new_y) == 750
    value_counts = new_y.to_series().value_counts()
    assert value_counts.values[1] / value_counts.values[0] == sampling_ratio
    pd.testing.assert_series_equal(value_counts, pd.Series([600, 150], index=[1, 0]), check_dtype=False)

    transform_X, transform_y = undersampler.transform(X, y)

    if data_type == "ww":
        X = X.to_dataframe().values
        y = y.to_series().values
    elif data_type == "pd":
        X = X.values
        y = y.values

    np.testing.assert_equal(X, transform_X.to_dataframe().values)
    np.testing.assert_equal(y, transform_y.to_series().values)


@pytest.mark.parametrize("dictionary,msg", [({'majority': 0.5}, "Lengths are diff"),
                                            ({'minority': 1}, "Lengths are diff"),
                                            ({0: 1, 1: 0.1}, "Dictionary keys are different from"),
                                            ({1: 0.1}, "Lengths are diff")])
def test_undersampler_sampling_dict_errors(dictionary, msg):
    X = np.array([[i] for i in range(1000)])
    y = np.array(["minority"] * 150 + ["majority"] * 850)

    undersampler = Undersampler(sampling_ratio_dict=dictionary)
    with pytest.raises(ValueError, match=msg):
        undersampler.fit_transform(X, y)


@pytest.mark.parametrize("dictionary,dictionary_values", [({0: 1, 1: 0.5}, {0: 150, 1: 300}),
                                                          ({0: 1, 1: 0.25}, {0: 150, 1: 600}),
                                                          ({0: 1, 1: 0.1}, {0: 150, 1: 850}),
                                                          ({0: 0.1, 1: 0.1}, {0: 150, 1: 850}),
                                                          ({0: 0.1, 1: 1}, {0: 150, 1: 150})])
def test_undersampler_sampling_dict(dictionary, dictionary_values):
    X = np.array([[i] for i in range(1000)])
    y = np.array([0] * 150 + [1] * 850)
    undersampler = Undersampler(sampling_ratio_dict=dictionary)
    new_X, new_y = undersampler.fit_transform(X, y)

    assert len(new_X) == sum(dictionary_values.values())
    assert new_y.to_series().value_counts().to_dict() == dictionary_values


def test_undersampler_dictionary_overrides_ratio():
    X = np.array([[i] for i in range(1000)])
    y = np.array([0] * 150 + [1] * 850)
    dictionary = {0: 1, 1: 0.5}
    expected_result = {0: 150, 1: 300}
    undersampler = Undersampler(sampling_ratio=0.1, sampling_ratio_dict=dictionary)
    new_X, new_y = undersampler.fit_transform(X, y)

    assert len(new_X) == sum(expected_result.values())
    assert new_y.to_series().value_counts().to_dict() == expected_result


def test_undersampler_sampling_dict_strings():
    X = np.array([[i] for i in range(1000)])
    y = np.array(["minority"] * 150 + ["majority"] * 850)
    dictionary = {"minority": 1, "majority": 0.5}
    expected_result = {"minority": 150, "majority": 300}
    undersampler = Undersampler(sampling_ratio_dict=dictionary)
    new_X, new_y = undersampler.fit_transform(X, y)

    assert len(new_X) == sum(expected_result.values())
    assert new_y.to_series().value_counts().to_dict() == expected_result
