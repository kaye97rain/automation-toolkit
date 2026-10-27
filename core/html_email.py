"""Building blocks for HTML report emails. Styles are inline because email clients ignore <style>."""

from datetime import date
from html import escape

import pandas as pd

from core.formatting import fmt

BLUE = "#1F4E78"
RED = "#cf222e"
GREEN = "#1a7f37"
AMBER = "#9a6700"
TH = f"text-align:left;padding:4px 10px;background:{BLUE};color:#fff;font-weight:600"
TD = "padding:4px 10px;border-bottom:1px solid #e5e5e5;vertical-align:top"


def html_table(df: pd.DataFrame, max_rows: int = 5) -> str:
    head = "".join(f'<th style="{TH}">{escape(str(c))}</th>' for c in df.columns)
    body = "".join(
        "<tr>" + "".join(f'<td style="{TD}">{escape(fmt(c, v))}</td>' for c, v in row.items()) + "</tr>"
        for _, row in df.head(max_rows).iterrows()
    )
    more = (f'<p style="color:#777;font-size:12px;margin:4px 0">...and {len(df) - max_rows} more '
            f"in the attachment</p>") if len(df) > max_rows else ""
    return f'<table style="border-collapse:collapse;font-size:13px"><tr>{head}</tr>{body}</table>{more}'


def bullets(items: list[str], color: str = "#222") -> str:
    return f'<ul style="margin:4px 0;color:{color}">' + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"


def heading(text: str, color: str = BLUE) -> str:
    return f'<h3 style="color:{color};margin:24px 0 6px">{escape(text)}</h3>'


def page(title: str, subtitle_html: str, body_html: str) -> str:
    """Wrap sections in a complete email body. subtitle_html may contain HTML."""
    return f"""\
<div style="font-family:Segoe UI,Arial,sans-serif;font-size:14px;color:#222;max-width:820px">
  <h2 style="color:{BLUE};margin-bottom:4px">{escape(title)}</h2>
  <p style="color:#777;margin-top:0">{date.today():%A, %B %d, %Y} &middot; {subtitle_html}</p>
  {body_html}
  <p style="color:#999;font-size:12px;margin-top:28px">Sent automatically by the automation toolkit.</p>
</div>"""
