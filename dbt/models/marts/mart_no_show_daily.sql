-- The dashboard's main table: one row per day, clinic and provider.
-- Leadership can roll this up to any level (day, clinic, provider) by summing
-- the counts and recomputing the rate. Never average the rates.

select
    appointment_date,
    appointment_weekday,
    clinic_name,
    provider_id,
    source_system,
    {{ no_show_metrics() }}
from {{ ref('fct_appointments') }}
group by all
