{# Use the schema names exactly as configured (staging, reference, ...)
   instead of dbt's default "<target>_<schema>" prefixing. #}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {{ custom_schema_name if custom_schema_name else target.schema }}
{%- endmacro %}
