import os
from collections.abc import Sequence


def _rolling_mean(values: Sequence[int | float], window: int = 7) -> list[float]:
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        result.append(sum(chunk) / len(chunk))
    return result


def generate_daily_cases_chart(data, output_dir=None, data_ref=None):
    """Generate a line chart of daily SRAG cases over the last 30 days.

    Includes a 7-day rolling average overlay and an annotation marking the
    peak day, following standard epidemiological surveillance visualisation.

    Args:
        data: List of dicts, each with keys ``dt_notific`` (date string) and
            ``casos`` (int) representing daily case counts.
        output_dir: Directory where the PNG image will be saved. Defaults to
            ``data/charts``.
        data_ref: Reference date string annotated at the bottom of the chart.
            If ``None``, no annotation is added.

    Returns:
        tuple[str, plotly.graph_objects.Figure]: A tuple containing the
            filepath of the saved PNG image and the Plotly Figure object.
    """
    import plotly.graph_objects as go

    if output_dir is None:
        output_dir = os.path.join("data", "charts")
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "daily_cases.png")

    fig = go.Figure()

    if data:
        dates = [row["dt_notific"] for row in data]
        cases = [int(row["casos"]) for row in data]

        fig.add_trace(
            go.Scatter(
                x=dates,
                y=cases,
                mode="lines+markers",
                name="Casos diários",
                marker_color="#1f77b4",
                line_color="#1f77b4",
                opacity=0.6,
            )
        )

        ma = _rolling_mean(cases)
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=ma,
                mode="lines",
                name="Média móvel 7 dias",
                line=dict(color="#d62728", width=2, dash="solid"),
            )
        )

        peak_idx = cases.index(max(cases))
        fig.add_annotation(
            x=dates[peak_idx],
            y=cases[peak_idx],
            text=f"Pico: {cases[peak_idx]}",
            showarrow=True,
            arrowhead=2,
            arrowcolor="#d62728",
            font=dict(size=10, color="#d62728"),
            yshift=10,
        )
    else:
        fig.add_annotation(
            text="Sem dados disponíveis",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20, color="gray"),
        )

    fig.update_layout(
        title="Casos diários de SRAG — Últimos 30 dias",
        xaxis_title="Data",
        yaxis_title="Número de casos",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    if data_ref is not None:
        fig.add_annotation(
            text=str(data_ref),
            xref="paper",
            yref="paper",
            x=1,
            y=-0.1,
            showarrow=False,
            font=dict(size=10, color="gray"),
        )

    try:
        fig.write_image(filepath, width=800, height=400)
    except Exception:
        filepath = ""

    return filepath, fig


def generate_monthly_cases_chart(data, output_dir=None, data_ref=None):
    """Generate a bar chart of monthly SRAG cases over the last 12 months.

    Annotates the peak month for quick identification of seasonal patterns.

    Args:
        data: List of dicts, each with keys ``dt_notific`` (date string) and
            ``casos`` (int) representing monthly case counts.
        output_dir: Directory where the PNG image will be saved. Defaults to
            ``data/charts``.
        data_ref: Reference date string annotated at the bottom of the chart.
            If ``None``, no annotation is added.

    Returns:
        tuple[str, plotly.graph_objects.Figure]: A tuple containing the
            filepath of the saved PNG image and the Plotly Figure object.
    """
    import plotly.graph_objects as go

    if output_dir is None:
        output_dir = os.path.join("data", "charts")
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "monthly_cases.png")

    fig = go.Figure()

    if data:
        dates = [row["dt_notific"] for row in data]
        cases = [int(row["casos"]) for row in data]

        fig.add_trace(
            go.Bar(
                x=dates,
                y=cases,
                name="Casos mensais",
                marker_color="#2ca02c",
            )
        )

        peak_idx = cases.index(max(cases))
        fig.add_annotation(
            x=dates[peak_idx],
            y=cases[peak_idx],
            text=f"Pico: {cases[peak_idx]}",
            showarrow=True,
            arrowhead=2,
            arrowcolor="#d62728",
            font=dict(size=10, color="#d62728"),
            yshift=10,
        )
    else:
        fig.add_annotation(
            text="Sem dados disponíveis",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=20, color="gray"),
        )

    fig.update_layout(
        title="Casos mensais de SRAG — Últimos 12 meses",
        xaxis_title="Data",
        yaxis_title="Número de casos",
        template="plotly_white",
    )

    if data_ref is not None:
        fig.add_annotation(
            text=str(data_ref),
            xref="paper",
            yref="paper",
            x=1,
            y=-0.1,
            showarrow=False,
            font=dict(size=10, color="gray"),
        )

    try:
        fig.write_image(filepath, width=800, height=400)
    except Exception:
        filepath = ""

    return filepath, fig
