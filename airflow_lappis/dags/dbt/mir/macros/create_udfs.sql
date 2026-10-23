{% macro create_udfs() %}

{#- O Cosmos roda este hook em todas as tasks em paralelo, e dois "create or
    replace function" simultâneos na mesma função dão "tuple concurrently
    updated". O lock serializa o hook e é liberado no fim da transação dele,
    antes de o modelo rodar. -#}
select pg_advisory_xact_lock(hashtext('{{ target.schema }}.create_udfs'));

create schema if not exists {{ target.schema }};

    {{ create_f_parse_dates() }}
    ;
    {{ create_f_format_nc() }}
    ;

{% endmacro %}
