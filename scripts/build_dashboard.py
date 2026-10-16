"""
Build reports/dashboard.html from the reporting marts.

One self-contained HTML file (no server, no external libraries) so it can be
opened locally, attached to an email, or hosted free on GitHub Pages.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
WAREHOUSE = ROOT / "data" / "warehouse.duckdb"
REPORTS = ROOT / "reports"
TEMPLATE = Path(__file__).with_name("dashboard_template.html")


def rows(con, sql: str) -> list[dict]:
    cur = con.execute(sql)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, (v.isoformat() if hasattr(v, "isoformat") else v for v in r))) for r in cur.fetchall()]


def main() -> None:
    con = duckdb.connect(str(WAREHOUSE), read_only=True)
    data = {
        "kpi": rows(con, """
            select sum(appointments) as appointments,
                   sum(no_shows) as no_shows,
                   round(sum(no_shows) / sum(arrived + no_shows), 4) as no_show_rate,
                   count(distinct clinic_name) as clinics,
                   count(distinct provider_id) as providers,
                   min(appointment_date) as first_date,
                   max(appointment_date) as last_date
            from reporting.mart_no_show_daily
        """)[0],
        "daily": rows(con, """
            select appointment_date as date,
                   sum(appointments) as appointments,
                   round(sum(no_shows) / sum(arrived + no_shows), 4) as rate
            from reporting.mart_no_show_daily
            group by 1 order by 1
        """),
        "weekday": rows(con, """
            select appointment_weekday as label, appointments, no_show_rate as rate
            from reporting.mart_no_show_by_weekday order by appointment_weekday_num
        """),
        "clinics": rows(con, """
            select clinic_name as label, appointments, no_show_rate as rate
            from reporting.mart_no_show_by_clinic
            where not is_small_sample
            order by no_show_rate desc
        """),
        "quality": rows(con, "select * from reporting.mart_data_quality"),
    }
    con.close()
    sms_path = REPORTS / "sms_by_lead_time.json"
    data["sms"] = json.loads(sms_path.read_text()) if sms_path.exists() else None

    REPORTS.mkdir(exist_ok=True)
    html = TEMPLATE.read_text(encoding="utf-8").replace("__DATA__", json.dumps(data).replace("</", "<\\/"))
    (REPORTS / "dashboard.html").write_text(html, encoding="utf-8")
    print(f"Wrote {REPORTS / 'dashboard.html'}")


if __name__ == "__main__":
    main()
