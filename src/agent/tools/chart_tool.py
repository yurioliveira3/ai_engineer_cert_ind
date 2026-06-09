import os

import plotly.graph_objects as go


def generate_daily_cases_chart(data, output_dir=None, data_ref=None):
    if output_dir is None:
        output_dir = os.path.join("data", "charts")
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "daily_cases.png")

    fig = go.Figure()

    if data:
        dates = [row["dt_notific"] for row in data]
        cases = [row["casos"] for row in data]
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=cases,
                mode="lines+markers",
                marker_color="#1f77b4",
                line_color="#1f77b4",
            )
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

    fig.write_image(filepath, width=800, height=400)

    return filepath, fig


def generate_monthly_cases_chart(data, output_dir=None, data_ref=None):
    if output_dir is None:
        output_dir = os.path.join("data", "charts")
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, "monthly_cases.png")

    fig = go.Figure()

    if data:
        dates = [row["dt_notific"] for row in data]
        cases = [row["casos"] for row in data]
        fig.add_trace(
            go.Bar(
                x=dates,
                y=cases,
                marker_color="#2ca02c",
            )
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

    fig.write_image(filepath, width=800, height=400)

    return filepath, fig
