{# The metric definition, written once and reused by every mart.

   no_show_rate = no-shows / appointments with a known outcome

   Appointments whose status couldn't be mapped (e.g. LWBS, "?", blank) are
   NOT in the denominator. Guessing them either way would bias the rate, so
   they're counted separately and shown on the dashboard instead. #}
{% macro no_show_metrics() %}
    count(*)                                              as appointments,
    count(*) filter (where visit_status = 'arrived')      as arrived,
    count(*) filter (where visit_status = 'no_show')      as no_shows,
    count(*) filter (where visit_status = 'unmapped')     as unmapped_status,
    round(
        count(*) filter (where visit_status = 'no_show')
        / nullif(count(*) filter (where has_known_outcome), 0),
        4
    )                                                     as no_show_rate
{% endmacro %}
