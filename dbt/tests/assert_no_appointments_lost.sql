-- Reconciliation test: every distinct appointment that arrived in a raw file
-- must appear exactly once in fct_appointments. Catches rows silently dropped
-- by a bad join or filter, and rows double-counted by a bad dedupe.
-- Returns a row (= test failure) if the counts differ.

with raw_ids as (

    select appointment_id as id from {{ source('raw', 'system_a_appointments') }}
    union
    select "Appt ID" from {{ source('raw', 'system_b_appointments') }}
    union
    select APPTNO from {{ source('raw', 'system_c_appointments') }}

)

select
    (select count(*) from raw_ids)                    as raw_distinct_appointments,
    (select count(*) from {{ ref('fct_appointments') }}) as fct_appointments
where (select count(*) from raw_ids) != (select count(*) from {{ ref('fct_appointments') }})
