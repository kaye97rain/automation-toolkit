import pandas as pd

from projects.weekly_sales_email.main import build_html, summarize


def make_sheets():
    raw = pd.DataFrame({"revenue": [100, 300], "region": ["North", "South"], "rep": ["Ana", "Ben"]})
    return {
        "Raw Data": raw,
        "By Month": pd.DataFrame({"month": ["2026-01", "2026-02"], "revenue": [100, 150]}),
        "By Region": pd.DataFrame({"region": ["South", "North"], "revenue": [300, 100]}),
        "By Rep": pd.DataFrame({"rep": ["Ben", "Ana"], "revenue": [300, 100]}),
    }


def test_summarize():
    s = summarize(make_sheets())
    assert s["total_revenue"] == 400
    assert s["orders"] == 2
    assert s["top_region"] == "South"
    assert s["latest_month"] == "2026-02"
    assert s["month_change_pct"] == 50


def test_build_html_contains_kpis():
    html = build_html(summarize(make_sheets()))
    assert "$400" in html
    assert "+50.0%" in html
