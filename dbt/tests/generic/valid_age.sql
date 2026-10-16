{# A tiny custom generic test: fail rows where an age is outside 0-115.
   Written by hand (instead of installing a package) so the logic is visible. #}
{% test valid_age(model, column_name) %}
    select *
    from {{ model }}
    where {{ column_name }} < 0 or {{ column_name }} > 115
{% endtest %}
