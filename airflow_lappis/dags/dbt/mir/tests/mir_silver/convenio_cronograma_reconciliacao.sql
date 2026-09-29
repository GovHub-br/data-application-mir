-- Falha se o cronograma da silver perder ou duplicar parcelas da bronze dos
-- convenios do MIR.
with
    bronze as (
        select count(*) as qtd, coalesce(sum(valor_parcela_crono_desembolso), 0) as valor
        from {{ ref("cronograma_desembolso") }}
        where nr_convenio in (select nr_convenio from {{ ref("convenio_mir") }})
    ),

    silver as (
        select count(*) as qtd, coalesce(sum(valor_previsto), 0) as valor
        from {{ ref("convenio_cronograma") }}
    )

select
    b.qtd as qtd_bronze,
    s.qtd as qtd_silver,
    b.valor as valor_bronze,
    s.valor as valor_silver
from bronze as b, silver as s
where b.qtd <> s.qtd or b.valor <> s.valor
