-- All three clinic systems stacked into one table, plus derived fields
-- every downstream model needs. One row per appointment.

with unioned as (

    select * from {{ ref('stg_system_a__appointments') }}
    union all by name
    select * from {{ ref('stg_system_b__appointments') }}
    union all by name
    select * from {{ ref('stg_system_c__appointments') }}

)

select
    *,
    -- Days between booking and the visit. Same-day bookings are 0.
    date_diff('day', cast(scheduled_at as date), appointment_date)  as lead_time_days,
    -- A handful of source rows were "booked" after the visit date: a data error.
    cast(scheduled_at as date) > appointment_date                   as is_booked_after_visit,
    dayname(appointment_date)                                       as appointment_weekday,
    isodow(appointment_date)                                        as appointment_weekday_num,
    visit_status = 'no_show'                                        as is_no_show,
    visit_status in ('arrived', 'no_show')                          as has_known_outcome
from unioned
