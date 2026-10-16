-- The clean, analysis-ready appointment table. Dashboards and analyses read
-- from here, never from raw or staging.

select
    appointment_id,
    source_system,
    patient_id,
    provider_id,
    clinic_name,
    scheduled_at,
    appointment_date,
    appointment_weekday,
    appointment_weekday_num,
    lead_time_days,
    patient_sex,
    patient_age,
    sms_reminder_sent,
    visit_status,
    raw_status,
    is_no_show,
    has_known_outcome,
    is_unmapped_status,
    is_booked_after_visit,
    _source_file
from {{ ref('int_appointments') }}
