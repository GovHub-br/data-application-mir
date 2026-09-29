-- Falha se alguma NE apontar para mais de um plano de acao na cascata de TED.
-- vinculo_ne_ted consolida por NE com max(); este teste garante que o max()
-- nao esconde conflito entre linhas da mesma NE.
with
    planos as (
        select distinct on (id_plano_acao) id_plano_acao, sq_instrumento
        from {{ ref("planos_acao_ted") }}
        where sq_instrumento is not null
        order by id_plano_acao, dt_ingest desc
    ),

    linhas as (
        select t.ne_ccor, p.id_plano_acao
        from {{ ref("ted_ne_transferencia") }} as t
        inner join planos as p on p.sq_instrumento = t.num_transf
    )

select ne_ccor, count(distinct id_plano_acao) as qtd_planos
from linhas
group by ne_ccor
having count(distinct id_plano_acao) > 1

union all

-- E falha se o modelo perder ou duplicar NEs em relacao a cascata.
select 'contagem divergente' as ne_ccor, 0 as qtd_planos
where
    (select count(*) from {{ ref("vinculo_ne_ted") }})
    <> (select count(distinct ne_ccor) from linhas)
