-- System B: front-desk software export.
-- Problems handled here:
--   * column names with spaces            -> quoted identifiers
--   * US dates ("05/17/2016", "04/29/2016 06:38 PM") -> strptime
--   * free-text statuses in many spellings -> lower(trim()) before the mapping join
--   * ~1% rows exported twice             -> keep one row per appointment
--   * unknown codes (LWBS, ?, blank)       -> flagged as unmapped, not guessed

with source as (

    select * from {{ source('raw', 'system_b_appointments') }}

),

deduplicated as (

    -- A duplicate is the same appointment ID sent more than once.
    -- Keep the earliest-loaded copy so results are deterministic.
    select *
    from source
    qualify row_number() over (
        partition by "Appt ID"
        order by _loaded_at, _source_file
    ) = 1

),

mapping as (

    select raw_status, standard_status
    from {{ ref('status_mapping') }}
    where source_system = 'system_b'

)

select
    'system_b'                                             as source_system,
    cast(d."Appt ID" as bigint)                            as appointment_id,
    cast(d."Patient ID" as bigint)                         as patient_id,
    d."Provider"                                           as provider_id,
    upper(trim(d."Location"))                              as clinic_name,
    strptime(d."Booked On", '%m/%d/%Y %I:%M %p')           as scheduled_at,
    cast(strptime(d."Appt Date", '%m/%d/%Y') as date)      as appointment_date,
    d."Sex"                                                as patient_sex,
    cast(d."Age" as integer)                               as patient_age,
    d."Text Reminder" = 'Yes'                              as sms_reminder_sent,
    d."Visit Status"                                       as raw_status,
    coalesce(mapping.standard_status, 'unmapped')          as visit_status,
    mapping.standard_status is null                        as is_unmapped_status,
    d._source_file,
    d._loaded_at

from deduplicated as d
left join mapping
    on lower(trim(coalesce(d."Visit Status", ''))) = mapping.raw_status
