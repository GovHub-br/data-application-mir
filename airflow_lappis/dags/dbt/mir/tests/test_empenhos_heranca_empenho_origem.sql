-- Falha se uma NE sem plano proprio cita um empenho de origem (rotina NSSALDO
-- de transferencia de saldo) que tem plano, e nao herdou esse plano. A
-- referencia so vale quando casa com uma unica NE de origem, e a origem que
-- tambem herdou fica fora (a heranca vai so um nivel).
with
    nes as (
        select
            ne_ccor,
            max(plano_acao) as plano_acao,
            bool_or(metodo like 'empenho de origem%') as herdou
        from {{ ref("empenhos_por_plano_acao") }}
        group by ne_ccor
    ),

    referencias as (
        select distinct e.ne_ccor, m[1] as ug_origem, m[2] as sufixo_origem
        from {{ ref("ppa_tesouro") }} as e
        cross join
            lateral regexp_match(
                e.ne_ccor_descricao, {{ regex_empenho_origem() }}, 'i'
            ) as m
        where e.ne_ccor <> '-9' and m is not null
    ),

    origens as (
        select
            r.ne_ccor,
            max(o.plano_acao) as plano_origem,
            bool_or(o.herdou) as origem_herdou
        from referencias as r
        inner join
            (select distinct ne_ccor from {{ ref("ppa_tesouro") }}) as todas
            on left(todas.ne_ccor, 6) = r.ug_origem
            and right(todas.ne_ccor, 12) = r.sufixo_origem
            and todas.ne_ccor <> r.ne_ccor
        left join nes as o on o.ne_ccor = todas.ne_ccor
        group by r.ne_ccor
        having count(distinct todas.ne_ccor) = 1
    )

select o.ne_ccor, d.plano_acao, o.plano_origem
from origens as o
left join nes as d on d.ne_ccor = o.ne_ccor
where
    o.plano_origem is not null
    and not o.origem_herdou
    and (d.plano_acao is null or (d.herdou and d.plano_acao <> o.plano_origem))
