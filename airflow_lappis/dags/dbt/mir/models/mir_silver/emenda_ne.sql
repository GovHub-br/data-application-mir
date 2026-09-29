{{ config(materialized="table") }}

-- NEs de emenda, uma linha por NE: a emenda (tg_emendas) e o parlamentar autor
-- com o partido vigente na data de emissao da NE. O parlamentar e achado pelo
-- nome em parlamentares_historico, com as prioridades do emendas_partidos:
-- 1 = filiacao vigente na data de emissao; 2 = nome encontrado, mas nenhuma
-- filiacao cobre a data (fica a mais proxima); 3 = nome nao encontrado
-- (parlamentar nulo). Filiacao sem data de fim vale como aberta (infinity),
-- sem depender da data de hoje.
with
    nes as (
        select
            ne_ccor,
            max(codigo_emenda) as codigo_emenda,
            -- A emissao da NE e a primeira data que nao e inscricao de RAP; NE
            -- so com linhas de RAP usa a primeira inscricao
            coalesce(
                min(data_emissao) filter (where not inscricao_rap), min(data_emissao)
            ) as data_emissao_ne
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null
        group by ne_ccor
    ),

    autores as (
        select distinct
            ne_ccor,
            autor_emendas_orcamento_descricao as emenda_descricao,
            autor_emendas_orcamento_nome as autor_nome,
            {{ name_formater("autor_emendas_orcamento_nome") }} as chave_join_nome
        from {{ ref("tg_emendas") }}
    ),

    candidatos as (
        select
            n.ne_ccor,
            n.codigo_emenda,
            n.data_emissao_ne,
            a.emenda_descricao,
            a.autor_nome,
            p.id_parlamentar,
            p.cargo_parlamentar,
            p.sigla_partido,
            case
                when p.id_parlamentar is null
                then 3
                when
                    n.data_emissao_ne >= p.data_filiacao::date
                    and n.data_emissao_ne
                    <= coalesce(p.data_desfiliacao::date, 'infinity'::date)
                then 1
                else 2
            end as prioridade_match,
            least(
                abs(n.data_emissao_ne - p.data_filiacao::date),
                abs(n.data_emissao_ne - p.data_desfiliacao::date)
            ) as distancia_dias
        from nes as n
        inner join autores as a on a.ne_ccor = n.ne_ccor
        left join
            {{ ref("parlamentares_historico") }} as p
            on p.chave_join_nome = a.chave_join_nome
    )

select distinct
    on (ne_ccor)
    ne_ccor,
    codigo_emenda,
    emenda_descricao,
    autor_nome,
    data_emissao_ne,
    id_parlamentar,
    cargo_parlamentar,
    sigla_partido,
    prioridade_match
from candidatos
order by
    ne_ccor, prioridade_match, distancia_dias nulls last, id_parlamentar, sigla_partido
