-- Data quality scorecard per clinic system. This is what you'd send each
-- clinic's IT contact: here's what's wrong with your export, and how much.

with raw_counts as (

    select 'system_a' as source_system, count(*) as raw_rows
    from {{ source('raw', 'system_a_appointments') }}
    union all
    select 'system_b', count(*) from {{ source('raw', 'system_b_appointments') }}
    union all
    select 'system_c', count(*) from {{ source('raw', 'system_c_appointments') }}

),

clean as (

    select
        source_system,
        count(*)                                                    as clean_rows,
        count(*) filter (where is_unmapped_status)                  as unmapped_status_rows,
        string_agg(distinct coalesce(nullif(trim(raw_status), ''), '(blank)'), ', ')
            filter (where is_unmapped_status)                       as unmapped_values,
        count(*) filter (where patient_age < 0 or patient_age > 115) as invalid_age_rows,
        count(*) filter (where is_booked_after_visit)               as booked_after_visit_rows
    from {{ ref('fct_appointments') }}
    group by source_system

),

skipped_files as (

    select system as source_system, count(*) as resent_files_skipped
    from {{ source('raw', 'load_manifest') }}
    where status = 'skipped_duplicate_content'
    group by system

)

select
    raw_counts.source_system,
    raw_counts.raw_rows,
    clean.clean_rows,
    raw_counts.raw_rows - clean.clean_rows          as duplicate_rows_removed,
    coalesce(skipped_files.resent_files_skipped, 0) as resent_files_skipped,
    clean.unmapped_status_rows,
    clean.unmapped_values,
    clean.invalid_age_rows,
    clean.booked_after_visit_rows
from raw_counts
join clean using (source_system)
left join skipped_files using (source_system)
order by source_system
