{% macro create_udfs() %}

create schema if not exists {{ target.schema }};

    {{ create_f_parse_financial_value() }}
    ;

{% endmacro %}
