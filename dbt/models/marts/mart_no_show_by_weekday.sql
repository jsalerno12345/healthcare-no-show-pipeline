-- No-show rate by day of week, Monday first.

select
    appointment_weekday_num,
    appointment_weekday,
    {{ no_show_metrics() }}
from {{ ref('fct_appointments') }}
group by all
order by appointment_weekday_num
