"""
Generate a small synthetic file with the same columns as the Kaggle dataset.

Used by CI (GitHub Actions) so the full pipeline and all tests run on every
push without downloading or redistributing the real data. The numbers are
fake; the shape, quirks and relationships (lead time, SMS rules) mimic the
real file closely enough to exercise every model and test.

    python scripts/make_sample_source.py            # writes data/source/KaggleV2-May-2016.csv
    python scripts/make_sample_source.py --rows 8000
"""

from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "source" / "KaggleV2-May-2016.csv"
NEIGHBOURHOODS = [
    "JARDIM DA PENHA", "MARIA ORTIZ", "RESISTÊNCIA", "JARDIM CAMBURI", "CENTRO",
    "ITARARÉ", "TABUAZEIRO", "SANTA MARTHA", "JESUS DE NAZARETH", "BONFIM",
    "SANTO ANTÔNIO", "SANTO ANDRÉ", "CARATOÍRA", "JABOUR", "SÃO PEDRO",
    "ILHA DO PRÍNCIPE", "NOVA PALESTINA", "DA PENHA", "ROMÃO", "GURIGICA",
]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=6000)
    args = parser.parse_args()
    rng = random.Random(7)

    start = datetime(2016, 4, 29)
    days = [start + timedelta(d) for d in range(41) if (start + timedelta(d)).weekday() < 5]
    rows = []
    for i in range(args.rows):
        appt_day = rng.choice(days)
        lead = rng.choice([0] * 35 + [1, 2] * 6 + list(range(3, 60)))
        scheduled = appt_day - timedelta(days=lead) + timedelta(hours=rng.randint(7, 18), minutes=rng.randint(0, 59))
        sms = int(lead >= 3 and rng.random() < 0.6)
        p_no_show = 0.05 if lead == 0 else min(0.40, 0.20 + lead * 0.003)
        if sms:
            p_no_show -= 0.05
        rows.append({
            "PatientId": float(rng.randint(10**10, 10**14)),
            "AppointmentID": 5_000_000 + i,
            "Gender": rng.choice("FFM"),
            "ScheduledDay": scheduled.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "AppointmentDay": appt_day.strftime("%Y-%m-%dT00:00:00Z"),
            "Age": -1 if i == 0 else rng.randint(0, 95),   # one bad age, like the real data
            "Neighbourhood": rng.choice(NEIGHBOURHOODS),
            "Scholarship": int(rng.random() < 0.1),
            "Hipertension": int(rng.random() < 0.2),
            "Diabetes": int(rng.random() < 0.07),
            "Alcoholism": int(rng.random() < 0.03),
            "Handcap": int(rng.random() < 0.02),
            "SMS_received": sms,
            "No-show": "Yes" if rng.random() < p_no_show else "No",
        })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(OUT, index=False)
    print(f"Wrote {len(rows):,} synthetic rows to {OUT}")


if __name__ == "__main__":
    main()
