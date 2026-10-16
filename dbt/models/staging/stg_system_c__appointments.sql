-- System C: legacy pipe-delimited export.
-- Problems handled here:
--   * cryptic column names (APPTNO, MRN, DR_CODE) -> renamed
--   * day-first dates ("17-May-2016")             -> strptime
--   * an "attended" flag instead of a status      -> Y = arrived, N = no_show via the seed

with source as (

    select * from {{ source('raw', 'system_c_appointments') }}

),

mapping as (

    select raw_status, standard_status
    from {{ ref('status_mapping') }}
    where source_system = 'system_c'

)

select
    'system_c'                                          as source_system,
    cast(source.APPTNO as bigint)                       as appointment_id,
    cast(source.MRN as bigint)                          as patient_id,
    source.DR_CODE                                      as provider_id,
    upper(trim(source.SITE))                            as clinic_name,
    strptime(source.BOOKED, '%d-%b-%Y %H:%M')           as scheduled_at,
    cast(strptime(source.APPT_DT, '%d-%b-%Y') as date)  as appointment_date,
    source.SEX                                          as patient_sex,
    cast(source.AGE as integer)                         as patient_age,
    source.SMS = 'Y'                                    as sms_reminder_sent,
    source.ATTENDED                                     as raw_status,
    coalesce(mapping.standard_status, 'unmapped')       as visit_status,
    mapping.standard_status is null                     as is_unmapped_status,
    source._source_file,
    source._loaded_at

from source
left join mapping
    on upper(trim(source.ATTENDED)) = mapping.raw_status
