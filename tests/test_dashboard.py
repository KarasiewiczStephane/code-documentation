"""Tests for the code documentation dashboard data generators."""

import pandas as pd

from src.dashboard.app import (
    generate_complexity_data,
    generate_cost_estimation,
    generate_function_complexity,
)


class TestComplexityData:
    def test_returns_dataframe(self) -> None:
        df = generate_complexity_data()
        assert isinstance(df, pd.DataFrame)

    def test_has_all_modules(self) -> None:
        df = generate_complexity_data()
        assert len(df) == 8

    def test_has_required_columns(self) -> None:
        df = generate_complexity_data()
        for col in [
            "module",
            "functions",
            "avg_complexity",
            "max_complexity",
            "lines_of_code",
            "doc_coverage",
        ]:
            assert col in df.columns

    def test_complexity_positive(self) -> None:
        df = generate_complexity_data()
        assert (df["avg_complexity"] > 0).all()

    def test_max_gte_avg(self) -> None:
        df = generate_complexity_data()
        assert (df["max_complexity"] >= df["avg_complexity"]).all()

    def test_doc_coverage_bounded(self) -> None:
        df = generate_complexity_data()
        assert (df["doc_coverage"] >= 0).all()
        assert (df["doc_coverage"] <= 1).all()

    def test_reproducible(self) -> None:
        df1 = generate_complexity_data(seed=99)
        df2 = generate_complexity_data(seed=99)
        pd.testing.assert_frame_equal(df1, df2)


class TestFunctionComplexity:
    def test_returns_dataframe(self) -> None:
        df = generate_function_complexity()
        assert isinstance(df, pd.DataFrame)

    def test_has_entries(self) -> None:
        df = generate_function_complexity()
        assert len(df) == 12

    def test_has_required_columns(self) -> None:
        df = generate_function_complexity()
        for col in [
            "function",
            "cyclomatic_complexity",
            "lines",
            "has_docstring",
            "parameters",
        ]:
            assert col in df.columns

    def test_complexity_positive(self) -> None:
        df = generate_function_complexity()
        assert (df["cyclomatic_complexity"] > 0).all()

    def test_lines_positive(self) -> None:
        df = generate_function_complexity()
        assert (df["lines"] > 0).all()


class TestCostEstimation:
    def test_returns_dataframe(self) -> None:
        df = generate_cost_estimation()
        assert isinstance(df, pd.DataFrame)

    def test_has_four_models(self) -> None:
        df = generate_cost_estimation()
        assert len(df) == 4

    def test_costs_positive(self) -> None:
        df = generate_cost_estimation()
        assert (df["total_cost"] > 0).all()

    def test_tokens_positive(self) -> None:
        df = generate_cost_estimation()
        assert (df["input_tokens"] > 0).all()
        assert (df["output_tokens"] > 0).all()
