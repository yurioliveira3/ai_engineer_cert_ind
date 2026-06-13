import os
from collections.abc import Sequence
from datetime import datetime


def _rolling_mean(values: Sequence[int | float], window: int = 7) -> list[float]:
    result = []
    for i in range(len(values)):
        start = max(0, i - window + 1)
        chunk = values[start : i + 1]
        result.append(sum(chunk) / len(chunk))
    return result


def _parse_date(value) -> datetime:
    return datetime.fromisoformat(str(value)[:10])


def _save_daily_png(data: list, filepath: str, data_ref=None) -> None:
    """Render daily cases chart to PNG using matplotlib (headless, no kaleido)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, ax = plt.subplots(figsize=(7, 3.5))

    if data:
        dates = [_parse_date(row["dt_notific"]) for row in data]
        cases = [int(row["casos"]) for row in data]
        ma = _rolling_mean(cases)

        ax.plot(dates, cases, color="#1f77b4", alpha=0.6, linewidth=1,
                marker="o", markersize=3, label="Casos diários")
        ax.plot(dates, ma, color="#d62728", linewidth=2, label="Média móvel 7d")

        ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m"))
        fig.autofmt_xdate(rotation=30)
        ax.legend(loc="upper left", fontsize=8)
    else:
        ax.text(0.5, 0.5, "Sem dados disponíveis", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="gray")

    ax.set_title("Casos diários de SRAG — Últimos 30 dias", fontsize=10)
    ax.set_xlabel("Data", fontsize=8)
    ax.set_ylabel("Casos", fontsize=8)
    ax.grid(True, alpha=0.3)
    if data_ref:
        fig.text(0.98, 0.01, str(data_ref), ha="right", fontsize=7, color="gray")

    plt.tight_layout()
    plt.savefig(filepath, dpi=120, bbox_inches="tight")
    plt.close(fig)


def _save_monthly_png(data: list, filepath: str, data_ref=None) -> None:
    """Render monthly cases bar chart to PNG using matplotlib (headless, no kaleido)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 3.5))

    if data:
        dates = [_parse_date(row["dt_notific"]) for row in data]
        labels = [d.strftime("%b/%Y") for d in dates]
        cases = [int(row["casos"]) for row in data]

        ax.bar(range(len(cases)), cases, color="#2ca02c", alpha=0.85)
        ax.set_xticks(range(len(cases)))
        ax.set_xticklabels(labels, rotation=40, ha="right", fontsize=7)

        ax.grid(True, alpha=0.3, axis="y")
    else:
        ax.text(0.5, 0.5, "Sem dados disponíveis", ha="center", va="center",
                transform=ax.transAxes, fontsize=12, color="gray")

    ax.set_title("Casos mensais de SRAG — Últimos 12 meses", fontsize=10)
    ax.set_xlabel("Mês", fontsize=8)
    ax.set_ylabel("Casos", fontsize=8)
    if data_ref:
        fig.text(0.98, 0.01, str(data_ref), ha="right", fontsize=7, color="gray")

    plt.tight_layout()
    plt.savefig(filepath, dpi=120, bbox_inches="tight")
    plt.close(fig)


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
        _save_daily_png(data, filepath, data_ref)
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
        _save_monthly_png(data, filepath, data_ref)
    except Exception:
        filepath = ""

    return filepath, fig
