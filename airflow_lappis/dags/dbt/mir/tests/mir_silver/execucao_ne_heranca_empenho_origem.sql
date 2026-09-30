-- Falha se uma NE sem instrumento proprio cita um empenho de origem (rotina
-- NSSALDO de transferencia de saldo) cujo instrumento proprio e conhecido, e
-- nao herdou esse instrumento. A referencia so vale quando casa com uma unica
-- NE de origem. Fica fora a NE com vinculo proprio (a regra mantem o dela) e a
-- origem que tambem herdou (a heranca vai so um nivel).
with
    nes as (
        select
            ne_ccor,
            max(sistema_instrumento) as sistema_instrumento,
            max(nr_instrumento) as nr_instrumento,
            max(metodo_vinculo) as metodo_vinculo
        from {{ ref("execucao_ne") }}
        group by ne_ccor
    ),

    referencias as (
        select distinct e.ne_ccor, m[1] as ug_origem, m[2] as sufixo_origem
        from {{ ref("ppa_tesouro") }} as e
        cross join
            lateral regexp_match(
                e.ne_ccor_descricao, {{ regex_empenho_origem() }}, 'i'
            ) as m
        where m is not null
    ),

    origens as (
        select
            r.ne_ccor,
            max(o.sistema_instrumento) as sistema_origem,
            max(o.nr_instrumento) as nr_origem,
            max(o.metodo_vinculo) as metodo_origem
        from referencias as r
        inner join
            nes as o
            on left(o.ne_ccor, 6) = r.ug_origem
            and right(o.ne_ccor, 12) = r.sufixo_origem
            and o.ne_ccor <> r.ne_ccor
        group by r.ne_ccor
        having count(distinct o.ne_ccor) = 1
    )

select d.ne_ccor, d.sistema_instrumento, o.sistema_origem, o.nr_origem
from origens as o
inner join nes as d on d.ne_ccor = o.ne_ccor
where
    o.sistema_origem <> 'Não identificado'
    and o.metodo_origem not like 'empenho de origem%'
    and (
        d.metodo_vinculo in ('nao_encontrado', 'ambiguo')
        or d.metodo_vinculo like 'empenho de origem%'
    )
    and (
        d.sistema_instrumento <> o.sistema_origem
        or d.nr_instrumento is distinct from o.nr_origem
    )
