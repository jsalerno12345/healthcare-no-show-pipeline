"""
Turn the single clean Kaggle file into realistic, messy nightly exports
from three different clinic systems.

Why: real healthcare data never arrives in one tidy file. Each clinic network
runs a different system, names columns differently, codes statuses differently,
and sometimes re-sends files. This script recreates that mess on purpose so the
pipeline has real problems to solve.

What it produces (one CSV per system per appointment day):
    data/clinic_exports/system_a/  -> clean-ish EHR export, numeric status codes
    data/clinic_exports/system_b/  -> human-entered text statuses, US dates, duplicates
    data/clinic_exports/system_c/  -> pipe-delimited, day-first dates, Y/N flags

Everything is seeded, so every run produces identical files.

Simulated (NOT in the original data) and documented in the README:
    - clinic system assignment (by neighbourhood)
    - provider_id (a few providers per neighbourhood)
    - status spelling variants, duplicates, and one re-sent file
"""

from __future__ import annotations

import argparse
import hashlib
import random
from pathlib import Path

import pandas as pd

SEED = 42
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "data" / "source" / "KaggleV2-May-2016.csv"
OUT_DIR = ROOT / "data" / "clinic_exports"


def stable_bucket(text: str, n: int) -> int:
    """Deterministic bucket for a string (Python's hash() changes between runs)."""
    return int(hashlib.md5(text.encode()).hexdigest(), 16) % n


def load_source(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={"No-show": "no_show"})
    df["appt_date"] = pd.to_datetime(df["AppointmentDay"]).dt.date
    df["scheduled_at"] = pd.to_datetime(df["ScheduledDay"])
    # Assign each neighbourhood to one of three clinic systems.
    df["system"] = df["Neighbourhood"].map(lambda n: "abc"[stable_bucket(n, 3)])
    # Simulate providers: 3-6 per neighbourhood, assigned per appointment.
    rng = random.Random(SEED)
    providers = {
        n: [f"PRV-{stable_bucket(n, 900) + 100:03d}-{i}" for i in range(3 + stable_bucket(n + "p", 4))]
        for n in df["Neighbourhood"].unique()
    }
    df["provider_id"] = [rng.choice(providers[n]) for n in df["Neighbourhood"]]
    return df


def export_system_a(df: pd.DataFrame, out: Path) -> None:
    """System A: an EHR export. Snake_case headers, ISO dates, numeric status codes."""
    status_code = {"No": 1, "Yes": 2}  # 1 = arrived, 2 = no show
    rows = pd.DataFrame(
        {
            "appointment_id": df["AppointmentID"],
            "patient_id": df["PatientId"].astype("int64"),
            "provider_id": df["provider_id"],
            "clinic_name": df["Neighbourhood"],
            "scheduled_ts": df["scheduled_at"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "appointment_date": df["appt_date"].astype(str),
            "patient_sex": df["Gender"],
            "patient_age": df["Age"],
            "sms_reminder_sent": df["SMS_received"],
            "status_code": df["no_show"].map(status_code),
        }
    )
    write_daily(rows, "appointment_date", out / "system_a", "appts_{day}.csv", sep=",")


def export_system_b(df: pd.DataFrame, out: Path, rng: random.Random) -> None:
    """System B: front-desk software. Title Case headers, US dates, free-text statuses,
    occasional duplicate rows, and a handful of values nobody mapped yet."""
    arrived = ["Arrived", "arrived", "ARRIVED", "Arrived ", "Checked In"]
    no_show = ["No Show", "no show", "No-Show", "NS", "noshow"]
    unknown = ["?", "LWBS", ""]  # typos / codes the data team has never seen

    def status(v: str) -> str:
        if rng.random() < 0.004:
            return rng.choice(unknown)
        return rng.choice(no_show if v == "Yes" else arrived)

    rows = pd.DataFrame(
        {
            "Appt ID": df["AppointmentID"],
            "Patient ID": df["PatientId"].astype("int64"),
            "Provider": df["provider_id"],
            "Location": df["Neighbourhood"].str.title(),
            "Booked On": df["scheduled_at"].dt.strftime("%m/%d/%Y %I:%M %p"),
            "Appt Date": pd.to_datetime(df["appt_date"]).dt.strftime("%m/%d/%Y"),
            "Sex": df["Gender"],
            "Age": df["Age"],
            "Text Reminder": df["SMS_received"].map({1: "Yes", 0: "No"}),
            "Visit Status": [status(v) for v in df["no_show"]],
            "_day": df["appt_date"].astype(str),
        }
    )
    # ~1% of rows exported twice (a classic re-export bug).
    dupes = rows.sample(frac=0.01, random_state=SEED)
    rows = pd.concat([rows, dupes]).sort_values(["_day", "Appt ID"])
    write_daily(rows, "_day", out / "system_b", "DailyVisits_{day}.csv", sep=",", drop=["_day"])


def export_system_c(df: pd.DataFrame, out: Path) -> None:
    """System C: legacy system. Pipe-delimited, day-first dates, Y/N 'attended' flag."""
    rows = pd.DataFrame(
        {
            "APPTNO": df["AppointmentID"],
            "MRN": df["PatientId"].astype("int64"),
            "DR_CODE": df["provider_id"],
            "SITE": df["Neighbourhood"].str.upper(),
            "BOOKED": df["scheduled_at"].dt.strftime("%d-%b-%Y %H:%M"),
            "APPT_DT": pd.to_datetime(df["appt_date"]).dt.strftime("%d-%b-%Y"),
            "SEX": df["Gender"],
            "AGE": df["Age"],
            "SMS": df["SMS_received"].map({1: "Y", 0: "N"}),
            "ATTENDED": df["no_show"].map({"No": "Y", "Yes": "N"}),
            "_day": df["appt_date"].astype(str),
        }
    )
    write_daily(rows, "_day", out / "system_c", "export_{day}.txt", sep="|", drop=["_day"])


def write_daily(rows, day_col, folder: Path, pattern: str, sep: str, drop=None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    for day, chunk in rows.groupby(day_col):
        chunk = chunk.drop(columns=drop or [])
        chunk.to_csv(folder / pattern.format(day=str(day).replace("-", "")), index=False, sep=sep)


def resend_one_file(out: Path) -> None:
    """System B re-sends one day's file under a new name — same rows, new file.
    A naive loader double-counts these appointments."""
    files = sorted((out / "system_b").glob("DailyVisits_*.csv"))
    original = files[len(files) // 2]
    resent = original.with_name(original.stem + "_RESEND.csv")
    resent.write_bytes(original.read_bytes())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    args = parser.parse_args()
    if not args.source.exists():
        raise SystemExit(
            f"Source file not found: {args.source}\n"
            "Download 'Medical Appointment No Shows' from Kaggle and save it there "
            "(see README, 'Get the data')."
        )
    rng = random.Random(SEED)
    df = load_source(args.source)
    export_system_a(df[df.system == "a"], OUT_DIR)
    export_system_b(df[df.system == "b"], OUT_DIR, rng)
    export_system_c(df[df.system == "c"], OUT_DIR)
    resend_one_file(OUT_DIR)
    for system in sorted(p.name for p in OUT_DIR.iterdir()):
        n = len(list((OUT_DIR / system).iterdir()))
        print(f"{system}: {n} files")


if __name__ == "__main__":
    main()
