-- Falha se, para algum tipo de movimento, a quantidade ou a soma na silver
-- divergir da bronze correspondente restrita aos convenios do MIR.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    bronze as (
        select
            'Desembolso federal' as tipo_movimento,
            count(*) as qtd,
            coalesce(sum(vl_desembolsado), 0) as valor
        from {{ ref("desembolso") }}
        where nr_convenio in (select nr_convenio from mir)
        union all
        select
            'Contrapartida depositada',
            count(*),
            coalesce(sum(vl_ingresso_contrapartida), 0)
        from {{ ref("ingresso_contrapartida") }}
        where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Desbloqueio', count(*), coalesce(sum(vl_desbloqueado), 0)
        from {{ ref("desbloqueio") }}
        where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Pagamento a fornecedor', count(*), coalesce(sum(vl_pago), 0)
        from {{ ref("pagamento") }}
        where nr_convenio in (select nr_convenio from mir)
        union all
        select 'Pagamento de tributo', count(*), coalesce(sum(vl_pag_tributos), 0)
        from {{ ref("pagamento_tributo") }}
        where nr_convenio in (select nr_convenio from mir)
    ),

    silver as (
        select tipo_movimento, count(*) as qtd, coalesce(sum(valor), 0) as valor
        from {{ ref("convenio_movimento_financeiro") }}
        group by tipo_movimento
    )

select
    b.tipo_movimento,
    b.qtd as qtd_bronze,
    s.qtd as qtd_silver,
    b.valor as valor_bronze,
    s.valor as valor_silver
from bronze as b
left join silver as s on s.tipo_movimento = b.tipo_movimento
where coalesce(s.qtd, 0) <> b.qtd or coalesce(s.valor, 0) <> b.valor
