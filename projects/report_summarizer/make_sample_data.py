"""Generate realistic mock business files in data/input/ to try the summarizer on.

    python -m projects.report_summarizer.make_sample_data

Creates:
  inventory.xlsx - stock levels per warehouse (matches the `inventory` rule)
  expenses.csv   - employee expense claims, messy like a real export (no rule: auto-detected)
"""

from datetime import date

import numpy as np
import pandas as pd

from core import config
from core.excel import write_sheets

TODAY = pd.Timestamp(date.today())
rng = np.random.default_rng(7)

CATALOG = {  # category -> {item: unit cost}
    "Electronics": {"USB-C Cable": 6.5, "Wireless Mouse": 18, "Mechanical Keyboard": 65, "27in Monitor": 210,
                    "HD Webcam": 45, "Laptop Stand": 32, "HDMI Adapter": 9.5, "Noise-Cancelling Headset": 120},
    "Office Supplies": {"Printer Paper (Ream)": 4.8, "Ballpoint Pens (Box of 12)": 3.2, "Stapler": 7.5,
                        "Sticky Notes (Pack)": 2.9, "File Folders (Box)": 11, "Whiteboard Markers (Set)": 6},
    "Furniture": {"Ergonomic Chair": 185, "Standing Desk": 340, "Filing Cabinet": 150, "Bookshelf": 95},
    "Cleaning": {"Hand Sanitizer 500ml": 3.5, "Disinfectant Wipes": 4.2, "Paper Towels (6 Rolls)": 7.8,
                 "Trash Bags (50ct)": 9},
    "Breakroom": {"Coffee Beans 1kg": 16, "Paper Cups (100ct)": 5.5, "Tea Assortment": 8,
                  "Bottled Water (24pk)": 6.4},
}
WAREHOUSES = ["North Hub", "Central Hub", "South Hub"]
SUPPLIERS = {"Electronics": ["TechSource Ltd", "Brightline Electronics"],
             "Office Supplies": ["PaperWorks Co", "OfficeHub Supply"], "Furniture": ["Workspace Interiors"],
             "Cleaning": ["CleanPro Distributors"], "Breakroom": ["Daily Grind Foods", "OfficeHub Supply"]}

EMPLOYEES = {"Sales": ["Alex Rivera", "Jordan Lee", "Sam Patel"], "Marketing": ["Taylor Kim", "Morgan Cruz"],
             "Operations": ["Casey Tan", "Riley Santos"], "IT": ["Jamie Reyes", "Avery Lim"],
             "Finance": ["Drew Garcia"]}
APPROVERS = {"Sales": "Pat Mendoza", "Marketing": "Chris Navarro", "Operations": "Lee Aquino",
             "IT": "Robin Castro", "Finance": "Dana Flores"}
EXPENSE_RANGES = {"Travel": (80, 900), "Meals": (15, 120), "Software": (10, 300),
                  "Office Supplies": (5, 150), "Training": (100, 1200)}


def make_inventory() -> pd.DataFrame:
    rows = []
    for c_i, (category, items) in enumerate(CATALOG.items(), start=1):
        for i_i, (item, cost) in enumerate(items.items(), start=1):
            for wh in WAREHOUSES:
                reorder = int(rng.integers(2, 9)) * 10
                qty = 0 if rng.random() < 0.06 else int(reorder * rng.uniform(0.3, 4.6))
                rows.append({
                    "SKU": f"{category[:3].upper()}-{c_i}{i_i:02d}-{wh[0]}",
                    "Item": item,
                    "Category": category,
                    "Warehouse": wh,
                    "Supplier": None if rng.random() < 0.05 else str(rng.choice(SUPPLIERS[category])),
                    "Qty On Hand": qty,
                    "Reorder Level": reorder,
                    "Unit Cost": round(cost * rng.uniform(0.95, 1.05), 2),
                    "Last Restocked": TODAY - pd.Timedelta(days=int(rng.integers(1, 150))),
                })
    df = pd.DataFrame(rows)
    return pd.concat([df, df.iloc[[5]]], ignore_index=True)  # one accidental duplicate, like real exports


def make_expenses() -> pd.DataFrame:
    rows = []
    for _ in range(220):
        dept = str(rng.choice(list(EMPLOYEES)))
        category = str(rng.choice(list(EXPENSE_RANGES)))
        amount = round(rng.uniform(*EXPENSE_RANGES[category]), 2)
        if rng.random() < 0.02:
            amount = -amount  # refunds
        rows.append({
            "Date": TODAY - pd.Timedelta(days=int(rng.integers(0, 120))),
            "Employee": str(rng.choice(EMPLOYEES[dept])),
            "Department": dept,
            "Category": category,
            "Amount": amount,
            "Approved By": None if rng.random() < 0.08 else APPROVERS[dept],
            "Receipt": "Yes" if rng.random() < 0.9 else "No",
        })
    df = pd.DataFrame(rows).sort_values("Date")
    df = pd.concat([df, df.sample(3, random_state=1)], ignore_index=True)  # accidental double submissions
    # Export as text the way many systems do: US dates and "$1,234.50" amounts
    df["Date"] = df["Date"].dt.strftime("%m/%d/%Y")
    df["Amount"] = df["Amount"].map(lambda a: f"-${-a:,.2f}" if a < 0 else f"${a:,.2f}")
    return df


if __name__ == "__main__":
    inv = write_sheets(config.INPUT_DIR / "inventory.xlsx", {"Inventory": make_inventory()})
    exp = config.INPUT_DIR / "expenses.csv"
    make_expenses().to_csv(exp, index=False)
    print(f"Created {inv}\nCreated {exp}")
