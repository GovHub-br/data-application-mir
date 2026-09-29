{#
    Parlamentar autor de uma emenda numa data. Acha o parlamentar pelo nome em
    parlamentares_historico, com as prioridades do emendas_partidos:
    1 = filiacao vigente na data; 2 = nome encontrado, mas nenhuma filiacao
    cobre a data (fica a mais proxima); 3 = nome nao encontrado (parlamentar
    nulo). Filiacao sem data de fim vale como aberta (infinity), sem depender
    da data de hoje. No dia da troca de partido as duas filiacoes cobrem a
    data; vale a mais recente.
    origem: nome de uma CTE com as colunas chave, autor_nome e data_referencia.
    Devolve uma linha por chave: chave, id_parlamentar, cargo_parlamentar,
    sigla_partido, prioridade_match.
#}
{% macro parlamentar_na_data(origem) %}
    select distinct
        on (o.chave)
        o.chave,
        p.id_parlamentar,
        p.cargo_parlamentar,
        p.sigla_partido,
        case
            when p.id_parlamentar is null
            then 3
            when
                o.data_referencia >= p.data_filiacao::date
                and o.data_referencia
                <= coalesce(p.data_desfiliacao::date, 'infinity'::date)
            then 1
            else 2
        end as prioridade_match
    from {{ origem }} as o
    left join
        {{ ref("parlamentares_historico") }} as p
        on p.chave_join_nome = {{ name_formater("o.autor_nome") }}
    order by
        o.chave,
        prioridade_match,
        least(
            abs(o.data_referencia - p.data_filiacao::date),
            abs(o.data_referencia - p.data_desfiliacao::date)
        ) nulls last,
        p.data_filiacao desc nulls last,
        p.id_parlamentar,
        p.sigla_partido
{% endmacro %}
