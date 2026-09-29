{#
    Parlamentar em SCD2 no grao parlamentar x cargo x partido (spec §4):
    valido_de = primeira filiacao ao partido, valido_ate = ultima desfiliacao
    (nula enquanto a filiacao esta aberta). Atributos descritivos vem da carga
    mais recente. O e-mail nao entra no gold.
#}
{% macro dim_parlamentar() %}
    select
        {{ surrogate_key(["id_parlamentar", "cargo_parlamentar", "sigla_partido"]) }}
        as sk_parlamentar,
        p.*
    from
        (
            select
                id_parlamentar,
                cargo_parlamentar,
                sigla_partido,
                (array_agg(nome_parlamentar order by dt_ingest desc))[
                    1
                ] as nome_parlamentar,
                (array_agg(uf_parlamentar order by dt_ingest desc))[1] as uf_parlamentar,
                (array_agg(url_foto order by dt_ingest desc))[1] as url_foto,
                (array_agg(url_logo_partido order by dt_ingest desc))[
                    1
                ] as url_logo_partido,
                min(data_filiacao)::date as valido_de,
                case
                    when bool_or(data_desfiliacao is null)
                    then null
                    else max(data_desfiliacao)::date
                end as valido_ate
            from {{ ref("parlamentares_historico") }}
            group by id_parlamentar, cargo_parlamentar, sigla_partido
        ) as p

    union all

    select
        -1::bigint,
        null,
        'Não identificado',
        'Não identificado',
        'Não identificado',
        null,
        null,
        null,
        null,
        null
{% endmacro %}
