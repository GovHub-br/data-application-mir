-- Para cada par NC+PTRES em nc_tesouro_desde_2026, a soma dos lados
-- ORIGEM e DESTINO deve ser igual: o mesmo crédito aparece nos dois
-- lados do lançamento, e o modelo nc_tesouro_mir só guarda o DESTINO.
-- Uma divergência indica dado incompleto na ingestão ou erro de
-- deduplicação upstream.
{{ config(severity="warn") }}

with
    por_lado as (
        select
            nc,
            ptres,
            dc,
            sum({{ parse_financial_value("valor_celula") }}) as soma
        from {{ source("siafi", "nc_tesouro_desde_2026") }}
        group by nc, ptres, dc
    ),
    origem as (
        select nc, ptres, soma from por_lado where dc = 'ORIGEM'
    ),
    destino as (
        select nc, ptres, soma from por_lado where dc = 'DESTINO'
    )

select
    coalesce(o.nc, d.nc) as nc,
    coalesce(o.ptres, d.ptres) as ptres,
    o.soma as soma_origem,
    d.soma as soma_destino,
    coalesce(d.soma, 0) - coalesce(o.soma, 0) as diferenca
from origem o
full join destino d using (nc, ptres)
where abs(coalesce(o.soma, 0) - coalesce(d.soma, 0)) >= 0.01
