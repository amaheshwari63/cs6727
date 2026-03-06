#!/usr/bin/env python3
"""Generate dense 65+ synthetic spending transactions from BLS CEX table 1300."""

from __future__ import annotations

import calendar
import csv
import json
import random
import re
import zipfile
import xml.etree.ElementTree as ET
import argparse
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple


NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
CONTROL_LABELS = {"", "Mean", "Share", "SE", "RSE"}
TARGET_COLS = {8: "65 years and older", 9: "65-74 years", 10: "75 years and older"}


@dataclass
class Adult:
    adult_id: str
    age_group: str
    age_years: int
    annual_budget: float


def parse_float(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    value = value.strip()
    if not value or value.lower() in {"b/", "c/"}:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def col_to_idx(col: str) -> int:
    num = 0
    for c in col:
        num = num * 26 + (ord(c) - 64)
    return num


def load_sheet_rows(xlsx_path: Path) -> Dict[int, Dict[int, str]]:
    with zipfile.ZipFile(xlsx_path) as zf:
        shared_strings: List[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            sst_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in sst_root.findall("m:si", NS):
                txt = "".join(t.text or "" for t in si.findall(".//m:t", NS))
                shared_strings.append(txt)

        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))
        sheet_data = sheet.find("m:sheetData", NS)
        if sheet_data is None:
            raise ValueError("sheet1.xml has no sheetData")

        rows: Dict[int, Dict[int, str]] = {}
        ref_re = re.compile(r"([A-Z]+)(\d+)")

        for row in sheet_data.findall("m:row", NS):
            rnum = int(row.attrib["r"])
            row_vals: Dict[int, str] = {}
            for cell in row.findall("m:c", NS):
                ref = cell.attrib.get("r", "")
                m = ref_re.match(ref)
                if not m:
                    continue
                col_idx = col_to_idx(m.group(1))
                v = cell.find("m:v", NS)
                if v is None:
                    continue
                val = v.text or ""
                if cell.attrib.get("t") == "s":
                    val = shared_strings[int(val)]
                row_vals[col_idx] = val
            rows[rnum] = row_vals
    return rows


def extract_age65plus_profile(rows: Dict[int, Dict[int, str]]) -> Tuple[Dict[str, float], Dict[str, Dict[str, float]]]:
    annual_means_by_group: Dict[str, float] = {}
    for col, group in TARGET_COLS.items():
        annual = parse_float(rows.get(51, {}).get(col))
        if annual is None:
            raise ValueError(f"Missing annual expenditure mean for {group}")
        annual_means_by_group[group] = annual

    item_means: Dict[str, Dict[str, float]] = {group: {} for group in TARGET_COLS.values()}
    # Expenditure detail rows start after row 54 and end before source note around row 637.
    for row_idx in range(55, 637):
        label = (rows.get(row_idx, {}).get(1) or "").strip()
        if label in CONTROL_LABELS:
            continue
        next_label = (rows.get(row_idx + 1, {}).get(1) or "").strip()
        if next_label != "Mean":
            continue

        for col, group in TARGET_COLS.items():
            mean_val = parse_float(rows.get(row_idx + 1, {}).get(col))
            if mean_val is not None and mean_val > 0:
                item_means[group][label] = mean_val

    return annual_means_by_group, item_means


def age_for_group(group: str, rng: random.Random) -> int:
    if group == "65-74 years":
        return rng.randint(65, 74)
    if group == "75 years and older":
        return rng.randint(75, 95)
    return rng.randint(65, 90)


def build_adults(annual_means: Dict[str, float], n: int, rng: random.Random) -> List[Adult]:
    # Ensure all requested 65+ age categories are represented.
    base_groups = ["65 years and older", "65-74 years", "75 years and older"]
    group_sequence = (base_groups * ((n // len(base_groups)) + 1))[:n]
    rng.shuffle(group_sequence)

    adults: List[Adult] = []
    for idx, group in enumerate(group_sequence, start=1):
        base = annual_means[group]
        multiplier = max(0.6, min(1.5, rng.lognormvariate(0.0, 0.2)))
        annual_budget = round(base * multiplier, 2)
        adults.append(
            Adult(
                adult_id=f"A{idx:02d}",
                age_group=group,
                age_years=age_for_group(group, rng),
                annual_budget=annual_budget,
            )
        )
    return adults


def allocate_cents(total_cents: int, n_parts: int, rng: random.Random) -> List[int]:
    weights = [rng.gammavariate(1.8, 1.0) for _ in range(n_parts)]
    total_w = sum(weights)
    raw = [w / total_w * total_cents for w in weights]
    base = [int(x) for x in raw]
    remainder = total_cents - sum(base)
    fracs = sorted(enumerate(raw), key=lambda x: x[1] - int(x[1]), reverse=True)
    for i in range(remainder):
        base[fracs[i % n_parts][0]] += 1
    return base


def make_merchant(category: str, rng: random.Random) -> str:
    stem = re.sub(r"[^A-Za-z0-9 ]+", "", category).strip()
    stem = re.sub(r"\s+", " ", stem)
    if not stem:
        stem = "General"
    words = stem.split()
    short = " ".join(words[:2])
    return f"{short} Shop {rng.randint(1, 9)}"


def generate_transactions(
    adults: List[Adult],
    item_means: Dict[str, Dict[str, float]],
    out_csv: Path,
    seed: int,
    year: int,
) -> Dict[str, object]:
    rng = random.Random(seed)
    tx_id = 1
    months = list(range(1, 13))
    total_amount = 0.0
    total_rows = 0

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "transaction_id",
                "adult_id",
                "age_years",
                "age_group_source",
                "transaction_date",
                "year",
                "month",
                "category",
                "merchant",
                "amount_usd",
                "monthly_budget_usd",
                "annual_budget_usd",
            ]
        )

        for adult in adults:
            categories = list(item_means[adult.age_group].keys())
            weights = [item_means[adult.age_group][c] for c in categories]
            monthly_budget = adult.annual_budget / 12.0
            monthly_budget_cents = int(round(monthly_budget * 100))

            for month in months:
                n_tx = rng.randint(48, 52)
                cats = rng.choices(categories, weights=weights, k=n_tx)
                cents_parts = allocate_cents(monthly_budget_cents, n_tx, rng)
                days_in_month = calendar.monthrange(year, month)[1]

                for category, cents in zip(cats, cents_parts):
                    day = rng.randint(1, days_in_month)
                    hour = rng.randint(7, 21)
                    minute = rng.randint(0, 59)
                    tx_dt = datetime(year, month, day, hour, minute, 0)
                    amount = cents / 100.0
                    total_amount += amount
                    total_rows += 1

                    writer.writerow(
                        [
                            f"T{tx_id:07d}",
                            adult.adult_id,
                            adult.age_years,
                            adult.age_group,
                            tx_dt.isoformat(timespec="minutes"),
                            year,
                            month,
                            category,
                            make_merchant(category, rng),
                            f"{amount:.2f}",
                            f"{monthly_budget_cents / 100.0:.2f}",
                            f"{adult.annual_budget:.2f}",
                        ]
                    )
                    tx_id += 1

    return {
        "row_count": total_rows,
        "total_amount_usd": round(total_amount, 2),
        "adults": [adult.__dict__ for adult in adults],
        "seed": seed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate dense synthetic transactions for 65+ adults from BLS CEX Table 1300 workbook."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("/Users/arvimahe/Downloads/reference-person-age-ranges-2024.xlsx"),
        help="Path to source XLSX workbook.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=Path("simulated_spending_65plus_10adults_2024.csv"),
        help="Output CSV path.",
    )
    parser.add_argument(
        "--output-metadata",
        type=Path,
        default=Path("simulated_spending_65plus_10adults_2024.metadata.json"),
        help="Output metadata JSON path.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=20260306,
        help="Random seed for reproducible generation.",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2024,
        help="Calendar year to stamp transaction dates.",
    )
    parser.add_argument(
        "--adults",
        type=int,
        default=10,
        help="Number of synthetic adults to generate.",
    )
    args = parser.parse_args()

    source = args.source
    out_csv = args.output_csv
    out_meta = args.output_metadata
    seed = args.seed
    year = args.year
    adults_n = args.adults

    rows = load_sheet_rows(source)
    annual_means, item_means = extract_age65plus_profile(rows)
    rng = random.Random(seed)
    adults = build_adults(annual_means, n=adults_n, rng=rng)
    summary = generate_transactions(adults, item_means, out_csv, seed=seed, year=year)

    metadata = {
        "source_workbook": str(source),
        "table_title": rows.get(1, {}).get(1, ""),
        "seed": seed,
        "year": year,
        "age_groups_used": list(TARGET_COLS.values()),
        "assumptions": [
            "Only age-based columns were used (65 years and older, 65-74 years, 75 years and older).",
            "Annual budget per synthetic adult was sampled around BLS age-group annual mean using a bounded lognormal multiplier.",
            "Annual budget was distributed uniformly across 12 months for each adult.",
            "Transactions per month were generated in the 48-52 range (about 50).",
            "Transaction categories were sampled proportionally to annual category means from the workbook.",
        ],
        "annual_mean_expenditure_by_age_group": annual_means,
        "category_count_by_age_group": {k: len(v) for k, v in item_means.items()},
        "simulation_summary": summary,
    }

    out_meta.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Seed: {seed}")
    print(f"Wrote {out_csv}")
    print(f"Wrote {out_meta}")
    print(f"Rows: {summary['row_count']}, Total amount: ${summary['total_amount_usd']:.2f}")


if __name__ == "__main__":
    main()
