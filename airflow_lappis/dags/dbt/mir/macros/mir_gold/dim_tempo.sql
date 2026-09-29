{#
    Dimensao de tempo compartilhada pelos marts (spec §4 e §6): um dia por
    linha, de inicio a fim, mais o membro -1 para fatos sem data.
#}
{% macro dim_tempo(inicio="2000-01-01", fim="2040-12-31") %}
    select
        {{ sk_tempo("d::date") }} as sk_tempo,
        d::date as data,
        extract(year from d)::integer as ano,
        case when extract(month from d) <= 6 then 1 else 2 end as semestre,
        extract(quarter from d)::integer as trimestre,
        extract(month from d)::integer as mes,
        (
            array[
                'Janeiro',
                'Fevereiro',
                'Março',
                'Abril',
                'Maio',
                'Junho',
                'Julho',
                'Agosto',
                'Setembro',
                'Outubro',
                'Novembro',
                'Dezembro'
            ]
        )[extract(month from d)::integer] as nome_mes,
        to_char(d, 'YYYY-MM') as ano_mes
    from generate_series('{{ inicio }}'::date, '{{ fim }}'::date, interval '1 day') as d

    union all

    select
        -1::bigint,
        null::date,
        null::integer,
        null::integer,
        null::integer,
        null::integer,
        'Não identificado',
        'Não identificado'
{% endmacro %}
