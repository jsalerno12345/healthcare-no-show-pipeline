-- Worked example (Week 1): standardize System A into the shared appointment shape.
-- Weeks 2 builds the same model for System B and System C — see docs/LEARNING.md.
--
-- Pattern used by every staging model:
--   1. rename columns to the shared names
--   2. cast text to real types
--   3. translate the raw status through the mapping seed
--   4. flag anything the mapping doesn't recognise instead of dropping it

with source as (

    select * from {{ source('raw', 'system_a_appointments') }}

),

mapping as (

    select raw_status, standard_status
    from {{ ref('status_mapping') }}
    where source_system = 'system_a'

)

select
    'system_a'                                   as source_system,
    cast(source.appointment_id as bigint)        as appointment_id,
    cast(source.patient_id as bigint)            as patient_id,
    source.provider_id,
    upper(trim(source.clinic_name))              as clinic_name,
    cast(source.scheduled_ts as timestamp)       as scheduled_at,
    cast(source.appointment_date as date)        as appointment_date,
    source.patient_sex,
    cast(source.patient_age as integer)          as patient_age,
    source.sms_reminder_sent = '1'               as sms_reminder_sent,
    source.status_code                           as raw_status,
    coalesce(mapping.standard_status, 'unmapped') as visit_status,
    mapping.standard_status is null              as is_unmapped_status,
    source._source_file,
    source._loaded_at

from source
left join mapping
    on source.status_code = mapping.raw_status
