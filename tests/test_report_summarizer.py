import logging

import pandas as pd

from projects.report_summarizer import profiler, rules


def test_detects_types_from_messy_text():
    raw = pd.DataFrame({
        "Date": ["01/05/2026", "02/10/2026", "03/15/2026"],
        "Amount": ["$1,200.00", "-$50.00", "$75.50"],
        "Dept": ["IT", "IT", "Sales"],
    })
    df, types = profiler.prepare(raw)
    assert types == {"Date": "date", "Amount": "number", "Dept": "category"}
    assert df["Amount"].sum() == 1225.5


def test_rule_calculates_breaks_down_and_alerts():
    df = pd.DataFrame({"Item": ["A", "B", "C"], "Qty On Hand": [0, 5, 50],
                       "Reorder Level": [10, 10, 10], "Unit Cost": [2.0, 3.0, 4.0]})
    rule = {
        "calculated": {"Stock Value": "`Qty On Hand` * `Unit Cost`"},
        "group_by": ["Item"],
        "sum": ["Stock Value"],
        "alerts": [{"name": "Low", "when": "`Qty On Hand` < `Reorder Level`", "show": ["Item"]}],
    }
    out = rules.apply_rule(df, rule, logging.getLogger("test"))
    assert out["df"]["Stock Value"].tolist() == [0, 15, 200]
    assert out["breakdowns"]["By Item"]["Item"].tolist() == ["C", "B", "A"]
    assert out["alerts"][0]["rows"]["Item"].tolist() == ["A", "B"]


def test_broken_rule_is_skipped_not_fatal():
    df = pd.DataFrame({"x": [1, 2]})
    rule = {"alerts": [{"name": "Bad", "when": "`missing column` > 1"}]}
    assert rules.apply_rule(df, rule, logging.getLogger("test"))["alerts"] == []


def test_find_rule_matches_filename_case_insensitive():
    found = rules.find_rule("Inventory_Oct.xlsx", {"inventory": {"match": "inventory*"}})
    assert found[0] == "inventory"
    assert rules.find_rule("expenses.csv", {"inventory": {"match": "inventory*"}}) is None
