#!/usr/bin/env python3
"""Generate reproducible synthetic transaction datasets for CS6727 research."""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import json
import math
import random
import re
import zipfile
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from xml.etree import ElementTree as ET

NS = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

TARGET_AGE_COLUMNS = {
    "H": "65 years and older",
    "I": "65-74 years",
    "J": "75 years and older",
}

SCAM_CATEGORIES = [
    "Investment taxes",
    "Investment fees",
    "Investment penalties",
]


@dataclass
class Profile:
    age_column: str
    age_group: str
    annual_total: float
    category_annual: Dict[str, float]
    category_probs: Dict[str, float]


@dataclass
class UserConfig:
    user_id: str
    profile: Profile


@dataclass
class ScenarioSpec:
    dataset_name: str
    month_states: Dict[str, Dict[int, str]]
    scenario_notes: Dict[str, object]


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def col_to_index(col: str) -> int:
    value = 0
    for ch in col:
        value = value * 26 + (ord(ch) - 64)
    return value


def parse_xlsx_rows(xlsx_path: Path):
    with zipfile.ZipFile(xlsx_path) as zf:
        shared = []
        shared_root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
        for si in shared_root.findall("a:si", NS):
            text = "".join(t.text or "" for t in si.findall(".//a:t", NS))
            shared.append(text)

        sheet = ET.fromstring(zf.read("xl/worksheets/sheet1.xml"))

    rows = {}
    styles = {}
    for row in sheet.findall(".//a:sheetData/a:row", NS):
        rnum = int(row.attrib["r"])
        vals = {}
        sty = {}
        for cell in row.findall("a:c", NS):
            ref = cell.attrib["r"]
            col = re.match(r"[A-Z]+", ref).group(0)
            sty[col] = cell.attrib.get("s", "")
            value_node = cell.find("a:v", NS)
            if value_node is None:
                continue
            raw = value_node.text or ""
            if cell.attrib.get("t") == "s":
                vals[col] = shared[int(raw)]
            else:
                vals[col] = raw
        rows[rnum] = vals
        styles[rnum] = sty
    return rows, styles


def as_float(value: str) -> float:
    text = normalize_text(value)
    if not text or text.lower() == "b/":
        return math.nan
    return float(text)


def extract_profiles(xlsx_path: Path) -> Dict[str, Profile]:
    rows, styles = parse_xlsx_rows(xlsx_path)

    header_row = rows[3]
    age_groups = {col: normalize_text(header_row[col]) for col in TARGET_AGE_COLUMNS}

    annual_total_by_col = {}
    for col in TARGET_AGE_COLUMNS:
        annual_total_by_col[col] = as_float(rows[51][col])

    # Use only top-level expenditure categories (style 10) to avoid double counting.
    top_level_categories = []
    for r in range(55, 571):
        label = normalize_text(rows.get(r, {}).get("A", ""))
        if not label:
            continue
        if rows.get(r + 1, {}).get("A") != "Mean":
            continue
        style = styles.get(r, {}).get("A", "")
        if style != "10":
            continue
        if label == "Average annual expenditures":
            continue
        means = {col: as_float(rows[r + 1].get(col, "")) for col in TARGET_AGE_COLUMNS}
        if any(math.isnan(v) or v <= 0 for v in means.values()):
            continue
        top_level_categories.append((label, means))

    profiles = {}
    for col in TARGET_AGE_COLUMNS:
        category_annual = {name: means[col] for name, means in top_level_categories}
        total = sum(category_annual.values())
        probs = {k: v / total for k, v in category_annual.items()}
        profiles[col] = Profile(
            age_column=col,
            age_group=age_groups[col],
            annual_total=annual_total_by_col[col],
            category_annual=category_annual,
            category_probs=probs,
        )
    return profiles


def month_to_start(month_index: int, start_year: int = 2024, start_month: int = 1) -> datetime:
    month0 = start_month - 1 + (month_index - 1)
    year = start_year + month0 // 12
    month = (month0 % 12) + 1
    return datetime(year, month, 1)


def random_timestamp_in_month(rng: random.Random, month_start: datetime) -> datetime:
    days = calendar.monthrange(month_start.year, month_start.month)[1]
    day = rng.randint(1, days)
    hour = rng.randint(8, 20)
    minute = rng.randint(0, 59)
    second = rng.randint(0, 59)
    return datetime(month_start.year, month_start.month, day, hour, minute, second)


def weighted_choice(rng: random.Random, keys: List[str], probs: List[float]) -> str:
    x = rng.random()
    c = 0.0
    for k, p in zip(keys, probs):
        c += p
        if x <= c:
            return k
    return keys[-1]


def generate_normal_transactions(
    rng: random.Random,
    user_id: str,
    profile: Profile,
    month_index: int,
    tx_count: int,
    payees_by_category: Dict[str, List[Tuple[str, str]]],
    seen_payees: set,
    tx_counter: int,
    dataset_name: str,
):
    month_start = month_to_start(month_index)
    cats = list(profile.category_probs.keys())
    probs = [profile.category_probs[c] for c in cats]

    assignments = [weighted_choice(rng, cats, probs) for _ in range(tx_count)]

    monthly_total_target = (profile.annual_total / 12.0) * rng.uniform(0.97, 1.03)

    base_amounts = []
    for category in assignments:
        expected_tx = max(1.0, tx_count * profile.category_probs[category])
        mean_ticket = max(5.0, (profile.category_annual[category] / 12.0) / expected_tx)
        sigma = 0.55
        mu = math.log(mean_ticket) - 0.5 * sigma * sigma
        base_amounts.append(rng.lognormvariate(mu, sigma))

    scale = monthly_total_target / max(1.0, sum(base_amounts))

    rows = []
    for i, (category, base_amt) in enumerate(zip(assignments, base_amounts), start=1):
        is_new_payee = False
        if (not payees_by_category[category]) or rng.random() < 0.02:
            payee_id = f"PAY_{user_id}_{category[:3].upper()}_{len(payees_by_category[category]) + 1:03d}"
            payee_name = f"{category} Merchant {len(payees_by_category[category]) + 1}"
            payees_by_category[category].append((payee_id, payee_name))
            is_new_payee = payee_id not in seen_payees
            seen_payees.add(payee_id)
        payee_id, payee_name = rng.choice(payees_by_category[category])

        tx_time = random_timestamp_in_month(rng, month_start)
        amount = round(max(1.0, base_amt * scale), 2)

        tx_counter += 1
        rows.append(
            {
                "dataset_name": dataset_name,
                "transaction_id": f"TX{tx_counter:08d}",
                "user_id": user_id,
                "month_index": month_index,
                "timestamp": tx_time.isoformat(),
                "age_group": profile.age_group,
                "age_column": profile.age_column,
                "month_state": "normal",
                "category": category,
                "payee_id": payee_id,
                "payee_name": payee_name,
                "payee_type": "regular",
                "amount_usd": amount,
                "is_new_payee": int(is_new_payee),
                "is_scam": 0,
                "scam_flag_new_payee": 0,
                "scam_flag_escalation": 0,
                "scam_flag_tax_fee_penalty": 0,
            }
        )
    return rows, tx_counter


def ensure_user_scam_payees(
    user_id: str,
    scam_payees: Dict[str, List[Tuple[str, str]]],
    occurrence_index: int,
):
    if not scam_payees[user_id]:
        scam_payees[user_id] = [
            (f"SCAM_{user_id}_TAX_001", "Crypto Recovery Tax Office"),
            (f"SCAM_{user_id}_FEE_001", "Digital Asset Release Fee Desk"),
        ]
    elif occurrence_index >= 2:
        next_idx = len(scam_payees[user_id]) + 1
        scam_payees[user_id].append(
            (f"SCAM_{user_id}_PEN_{next_idx:03d}", f"Investment Penalty Handler {next_idx}")
        )


def generate_scam_transactions(
    rng: random.Random,
    user_id: str,
    profile: Profile,
    month_index: int,
    tx_count: int,
    payees_by_category: Dict[str, List[Tuple[str, str]]],
    seen_payees: set,
    scam_payees: Dict[str, List[Tuple[str, str]]],
    scam_occurrence_index: int,
    prior_scam_amount_by_user: Dict[str, float],
    tx_counter: int,
    dataset_name: str,
):
    month_start = month_to_start(month_index)

    ensure_user_scam_payees(user_id, scam_payees, scam_occurrence_index)
    active_scam_payees = scam_payees[user_id]

    scam_ratio = min(0.2 + 0.1 * (scam_occurrence_index - 1), 0.8)
    scam_tx_count = max(10, int(round(tx_count * scam_ratio)))
    normal_tx_count = tx_count - scam_tx_count

    normal_rows, tx_counter = generate_normal_transactions(
        rng,
        user_id,
        profile,
        month_index,
        normal_tx_count,
        payees_by_category,
        seen_payees,
        tx_counter,
        dataset_name,
    )

    monthly_total_target = (profile.annual_total / 12.0) * rng.uniform(1.06, 1.26)
    scam_budget = monthly_total_target * min(0.35 + 0.12 * (scam_occurrence_index - 1), 0.85)

    base_amounts = [rng.lognormvariate(5.2 + 0.08 * scam_occurrence_index, 0.45) for _ in range(scam_tx_count)]
    scale = scam_budget / max(1.0, sum(base_amounts))

    scam_rows = []
    monthly_scam_total = 0.0
    for base_amt in base_amounts:
        payee_id, payee_name = rng.choice(active_scam_payees)
        category = rng.choice(SCAM_CATEGORIES)

        is_new_payee = payee_id not in seen_payees
        if is_new_payee:
            seen_payees.add(payee_id)

        tx_counter += 1
        amount = round(max(50.0, base_amt * scale), 2)
        monthly_scam_total += amount

        scam_rows.append(
            {
                "dataset_name": dataset_name,
                "transaction_id": f"TX{tx_counter:08d}",
                "user_id": user_id,
                "month_index": month_index,
                "timestamp": random_timestamp_in_month(rng, month_start).isoformat(),
                "age_group": profile.age_group,
                "age_column": profile.age_column,
                "month_state": "scam",
                "category": category,
                "payee_id": payee_id,
                "payee_name": payee_name,
                "payee_type": "new_high_risk",
                "amount_usd": amount,
                "is_new_payee": int(is_new_payee),
                "is_scam": 1,
                "scam_flag_new_payee": int(is_new_payee),
                "scam_flag_escalation": int(
                    scam_occurrence_index > 1 and monthly_scam_total > prior_scam_amount_by_user.get(user_id, 0.0)
                ),
                "scam_flag_tax_fee_penalty": 1,
            }
        )

    prior_scam_amount_by_user[user_id] = monthly_scam_total

    all_rows = normal_rows + scam_rows
    all_rows.sort(key=lambda r: r["timestamp"])
    return all_rows, tx_counter


def build_user_configs(profiles: Dict[str, Profile], user_count: int = 100) -> List[UserConfig]:
    # Deterministic round-robin assignment across 65+ age categories.
    age_cols = ["H", "I", "J"]
    users = []
    for idx in range(user_count):
        user_id = f"U{idx + 1:03d}"
        col = age_cols[idx % len(age_cols)]
        users.append(UserConfig(user_id=user_id, profile=profiles[col]))
    return users


def scenario_dataset1(users: List[UserConfig]) -> ScenarioSpec:
    month_states = {}
    all_user_ids = [u.user_id for u in users]
    non_scam_users = all_user_ids[:80]
    scam_tail_users = all_user_ids[80:100]

    for uid in non_scam_users:
        month_states[uid] = {m: "normal" for m in range(1, 19)}

    # First 12 months normal for all users; final 6 months include fraud indicators for 20 users.
    for uid in scam_tail_users:
        states = {m: "normal" for m in range(1, 13)}
        for month in range(13, 19):
            states[month] = "scam"
        month_states[uid] = states

    return ScenarioSpec(
        dataset_name="cs6727_DS1",
        month_states=month_states,
        scenario_notes={
            "non_scam_users_18m": len(non_scam_users),
            "scam_users_first12_normal_last6_scam": len(scam_tail_users),
        },
    )


def scenario_dataset2(users: List[UserConfig], rng: random.Random) -> ScenarioSpec:
    del rng
    month_states = {}
    user_ids = [u.user_id for u in users]
    non_scam_users = user_ids[:80]
    all_month_scam_users = user_ids[80:100]

    for uid in non_scam_users:
        month_states[uid] = {m: "normal" for m in range(1, 19)}

    for uid in all_month_scam_users:
        states = {m: "scam" for m in range(1, 19)}
        for m in range(1, 19):
            states[m] = "scam"
        month_states[uid] = states

    return ScenarioSpec(
        dataset_name="cs6727_DS2",
        month_states=month_states,
        scenario_notes={
            "non_scam_users_18m": len(non_scam_users),
            "scam_users_18m": len(all_month_scam_users),
        },
    )


def generate_dataset(users: List[UserConfig], scenario: ScenarioSpec, seed: int) -> List[dict]:
    rng = random.Random(seed)
    rows = []
    tx_counter = 0

    payees_by_user_category = {
        user.user_id: defaultdict(list) for user in users
    }
    seen_payees = {user.user_id: set() for user in users}
    scam_payees = defaultdict(list)
    prior_scam_amount = {}

    # Seed regular payee pools per user/category.
    for user in users:
        for cat in user.profile.category_probs:
            for i in range(5):
                pid = f"PAY_{user.user_id}_{cat[:3].upper()}_{i + 1:03d}"
                pname = f"{cat} Merchant {i + 1}"
                payees_by_user_category[user.user_id][cat].append((pid, pname))
                seen_payees[user.user_id].add(pid)

    for user in users:
        scam_occurrence_index = 0
        for month_index in range(1, 19):
            state = scenario.month_states[user.user_id][month_index]
            if state == "normal":
                month_rows, tx_counter = generate_normal_transactions(
                    rng,
                    user.user_id,
                    user.profile,
                    month_index,
                    tx_count=50,
                    payees_by_category=payees_by_user_category[user.user_id],
                    seen_payees=seen_payees[user.user_id],
                    tx_counter=tx_counter,
                    dataset_name=scenario.dataset_name,
                )
            else:
                scam_occurrence_index += 1
                month_rows, tx_counter = generate_scam_transactions(
                    rng,
                    user.user_id,
                    user.profile,
                    month_index,
                    tx_count=50,
                    payees_by_category=payees_by_user_category[user.user_id],
                    seen_payees=seen_payees[user.user_id],
                    scam_payees=scam_payees,
                    scam_occurrence_index=scam_occurrence_index,
                    prior_scam_amount_by_user=prior_scam_amount,
                    tx_counter=tx_counter,
                    dataset_name=scenario.dataset_name,
                )
            rows.extend(month_rows)

    rows.sort(key=lambda r: (r["user_id"], r["month_index"], r["timestamp"], r["transaction_id"]))
    return rows


def write_csv(path: Path, rows: List[dict]):
    if not rows:
        raise ValueError("No rows to write")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def summarize(rows: List[dict]) -> dict:
    users = sorted({r["user_id"] for r in rows})
    scam_rows = sum(r["is_scam"] for r in rows)
    by_state = defaultdict(int)
    for r in rows:
        by_state[r["month_state"]] += 1
    return {
        "rows": len(rows),
        "users": len(users),
        "months_per_user": 18,
        "transactions_per_user_month": 50,
        "scam_rows": scam_rows,
        "normal_rows": len(rows) - scam_rows,
        "month_state_counts": dict(sorted(by_state.items())),
    }


def main():
    parser = argparse.ArgumentParser(description="Generate CS6727 synthetic datasets")
    parser.add_argument(
        "--source-xlsx",
        type=Path,
        default=Path("/Users/arvimahe/Downloads/reference-person-age-ranges-2024.xlsx"),
        help="Path to BLS reference spreadsheet",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data"))
    parser.add_argument("--seed", type=int, default=6727)
    parser.add_argument(
        "--metadata-json",
        type=Path,
        default=Path("data/generation_metadata.json"),
        help="Output JSON with row counts, hashes, and config",
    )
    args = parser.parse_args()

    profiles = extract_profiles(args.source_xlsx)
    users = build_user_configs(profiles, user_count=100)

    ds1_spec = scenario_dataset1(users)
    ds2_spec = scenario_dataset2(users, random.Random(args.seed + 200))

    ds1_rows = generate_dataset(users, ds1_spec, seed=args.seed + 1)
    ds2_rows = generate_dataset(users, ds2_spec, seed=args.seed + 2)

    ds1_path = args.output_dir / "cs6727_DS1.csv"
    ds2_path = args.output_dir / "cs6727_DS2.csv"
    write_csv(ds1_path, ds1_rows)
    write_csv(ds2_path, ds2_rows)

    metadata = {
        "seed": args.seed,
        "source_xlsx": str(args.source_xlsx),
        "output_dir": str(args.output_dir),
        "source_age_columns": TARGET_AGE_COLUMNS,
        "dataset_files": {
            "cs6727_DS1": {
                "path": str(ds1_path),
                "sha256": sha256_file(ds1_path),
                **summarize(ds1_rows),
                "scenario": ds1_spec.scenario_notes,
            },
            "cs6727_DS2": {
                "path": str(ds2_path),
                "sha256": sha256_file(ds2_path),
                **summarize(ds2_rows),
                "scenario": ds2_spec.scenario_notes,
            },
        },
        "profiles": {
            key: {
                "age_group": profile.age_group,
                "annual_total": profile.annual_total,
                "top_level_categories": profile.category_annual,
            }
            for key, profile in profiles.items()
        },
    }

    args.metadata_json.parent.mkdir(parents=True, exist_ok=True)
    args.metadata_json.write_text(json.dumps(metadata, indent=2), encoding="utf-8")

    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
