"""Streamlit dashboard for code documentation analysis.

Displays code complexity metrics, documentation coverage,
call graph statistics, and API cost estimation using synthetic data.

Run with: streamlit run src/dashboard/app.py
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

MODULE_NAMES = [
    "parsers.python_parser",
    "parsers.js_parser",
    "analysis.complexity",
    "analysis.call_graph",
    "generators.docstring_gen",
    "output.markdown",
    "output.html",
    "utils.config",
]


def generate_complexity_data(seed: int = 42) -> pd.DataFrame:
    """Generate synthetic code complexity metrics per module."""
    rng = np.random.default_rng(seed)
    rows = []
    for mod in MODULE_NAMES:
        num_funcs = int(rng.integers(5, 25))
        avg_cc = round(rng.uniform(1.5, 12.0), 2)
        max_cc = round(avg_cc + rng.uniform(2, 8), 2)
        loc = int(rng.integers(80, 500))
        rows.append(
            {
                "module": mod,
                "functions": num_funcs,
                "avg_complexity": avg_cc,
                "max_complexity": max_cc,
                "lines_of_code": loc,
                "doc_coverage": round(rng.uniform(0.3, 1.0), 2),
            }
        )
    return pd.DataFrame(rows)


def generate_function_complexity(seed: int = 42) -> pd.DataFrame:
    """Generate synthetic per-function complexity data."""
    rng = np.random.default_rng(seed)
    functions = [
        "parse_module",
        "extract_docstring",
        "build_call_graph",
        "analyze_imports",
        "generate_docs",
        "render_html",
        "compute_metrics",
        "resolve_types",
        "format_output",
        "validate_ast",
        "traverse_tree",
        "merge_results",
    ]
    rows = []
    for func in functions:
        cc = round(rng.uniform(1, 18), 1)
        rows.append(
            {
                "function": func,
                "cyclomatic_complexity": cc,
                "lines": int(rng.integers(10, 120)),
                "has_docstring": bool(rng.random() > 0.3),
                "parameters": int(rng.integers(0, 8)),
            }
        )
    return pd.DataFrame(rows)


def generate_cost_estimation(seed: int = 42) -> pd.DataFrame:
    """Generate synthetic API cost estimation data."""
    rng = np.random.default_rng(seed)
    models = ["claude-3-5-sonnet", "gpt-4o", "gpt-4o-mini", "claude-3-haiku"]
    rows = []
    for model in models:
        input_tokens = int(rng.integers(50000, 200000))
        output_tokens = int(rng.integers(20000, 80000))
        rate = rng.uniform(0.5, 15.0) / 1_000_000
        rows.append(
            {
                "model": model,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "total_cost": round((input_tokens + output_tokens) * rate, 4),
                "avg_time_per_file": round(rng.uniform(1.5, 8.0), 2),
            }
        )
    return pd.DataFrame(rows)


def render_header() -> None:
    """Render the dashboard header."""
    st.title("Code Documentation Generator Dashboard")
    st.caption(
        "Complexity analysis, documentation coverage tracking, "
        "and LLM cost estimation for automated doc generation"
    )


def render_summary_metrics(complexity_df: pd.DataFrame, cost_df: pd.DataFrame) -> None:
    """Render top-level summary metric cards."""
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Modules Analyzed", len(complexity_df))
    col2.metric(
        "Avg Complexity",
        f"{complexity_df['avg_complexity'].mean():.1f}",
    )
    col3.metric(
        "Doc Coverage",
        f"{complexity_df['doc_coverage'].mean():.0%}",
    )
    col4.metric("Est. Total Cost", f"${cost_df['total_cost'].sum():.2f}")


def render_complexity_heatmap(complexity_df: pd.DataFrame) -> None:
    """Render module complexity heatmap."""
    st.subheader("Module Complexity Overview")
    fig = px.bar(
        complexity_df.sort_values("avg_complexity", ascending=False),
        x="module",
        y="avg_complexity",
        color="avg_complexity",
        color_continuous_scale="RdYlGn_r",
        text="avg_complexity",
    )
    fig.update_layout(
        height=350,
        margin={"l": 40, "r": 20, "t": 30, "b": 80},
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_coverage_chart(complexity_df: pd.DataFrame) -> None:
    """Render documentation coverage chart."""
    st.subheader("Documentation Coverage by Module")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=complexity_df["module"],
            y=complexity_df["doc_coverage"],
            marker_color=[
                "#4CAF50" if c >= 0.8 else "#FF9800" if c >= 0.5 else "#F44336"
                for c in complexity_df["doc_coverage"]
            ],
            text=complexity_df["doc_coverage"].apply(lambda x: f"{x:.0%}"),
            textposition="auto",
        )
    )
    fig.update_layout(
        yaxis={"tickformat": ".0%", "range": [0, 1.1]},
        height=350,
        margin={"l": 40, "r": 20, "t": 30, "b": 80},
        xaxis_tickangle=-45,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_function_ranking(func_df: pd.DataFrame) -> None:
    """Render most complex functions ranking."""
    st.subheader("Most Complex Functions")
    sorted_df = func_df.sort_values("cyclomatic_complexity", ascending=False).head(10)
    fig = px.bar(
        sorted_df,
        x="cyclomatic_complexity",
        y="function",
        orientation="h",
        color="cyclomatic_complexity",
        color_continuous_scale="Reds",
    )
    fig.update_layout(
        height=350,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_cost_comparison(cost_df: pd.DataFrame) -> None:
    """Render API cost comparison chart."""
    st.subheader("LLM Cost Estimation")
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=cost_df["model"],
            y=cost_df["total_cost"],
            text=cost_df["total_cost"].apply(lambda x: f"${x:.2f}"),
            textposition="auto",
            marker_color=["#2196F3", "#FF9800", "#4CAF50", "#9C27B0"],
        )
    )
    fig.update_layout(
        yaxis_title="Estimated Cost ($)",
        height=350,
        margin={"l": 40, "r": 20, "t": 30, "b": 40},
    )
    st.plotly_chart(fig, use_container_width=True)


def main() -> None:
    """Main dashboard entry point."""
    render_header()

    complexity_df = generate_complexity_data()
    func_df = generate_function_complexity()
    cost_df = generate_cost_estimation()

    render_summary_metrics(complexity_df, cost_df)
    st.markdown("---")

    render_complexity_heatmap(complexity_df)

    col_left, col_right = st.columns(2)
    with col_left:
        render_coverage_chart(complexity_df)
    with col_right:
        render_function_ranking(func_df)

    st.markdown("---")
    render_cost_comparison(cost_df)


if __name__ == "__main__":
    main()
