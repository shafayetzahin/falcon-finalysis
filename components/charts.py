"""Consistent interactive chart styling, with explicit scale labels."""
import plotly.graph_objects as go
import pandas as pd

COLORS = ['#008C95', '#173859', '#5A8DDA', '#CF9650', '#A36394']


def line_chart(df: pd.DataFrame, columns: list[str], title: str, unit: str = '', dark: bool = False) -> go.Figure:
    fig = go.Figure()
    for i, col in enumerate(columns):
        values = df[col] * (100 if unit == '%' else 1/1e6 if unit == 'millions' else 1)
        fig.add_trace(go.Scatter(x=[str(int(y)) for y in df.index], y=values, name=col,
                                 mode='lines+markers', line=dict(color=COLORS[i % len(COLORS)], width=3),
                                 marker=dict(size=7), connectgaps=False,
                                 hovertemplate='%{x}<br>%{y:,.2f} ' + unit + '<extra>%{fullData.name}</extra>'))
    fig.update_layout(title=title, height=340, template='plotly_dark' if dark else 'plotly_white',
                      paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                      margin=dict(l=15, r=20, t=55, b=20), hovermode='x unified',
                      legend=dict(orientation='h', y=-.15), yaxis_title=unit, xaxis_title=None)
    if dark:
        fig.update_layout(font_color='#E8EEF5')
    return fig
