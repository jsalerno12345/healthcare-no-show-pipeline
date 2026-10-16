-- No-show rate per clinic across the whole period, ranked.
-- Small clinics are flagged: a 40% rate on 10 visits isn't a pattern.

select
    clinic_name,
    source_system,
    {{ no_show_metrics() }},
    count(*) filter (where has_known_outcome) < 100 as is_small_sample
from {{ ref('fct_appointments') }}
group by all
order by no_show_rate desc
