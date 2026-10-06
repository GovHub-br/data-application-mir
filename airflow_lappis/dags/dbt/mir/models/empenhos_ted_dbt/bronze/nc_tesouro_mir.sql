{{ config(materialized='table') }}

-- Notas de credito do MIR (Tesouro Gerencial), uma linha por movimento, so NCs
-- entre o MIR e outros orgaos: "enviadas" (emitente MIR) e "recebidas"
-- (favorecido MIR: devolucoes e creditos recebidos).
-- Ate 2025 a fonte e o lancamento (lado do MIR): o valor e o movimento
-- liquido, que ja vem com sinal, e o tipo sai do sinal e do relatorio (o
-- relatorio nao traz o evento: com ele as linhas da NC cruzariam com os
-- lancamentos). Uma devolucao em "enviadas" ou uma anulacao em "recebidas"
-- ficam, por isso, como anulacao e devolucao, respectivamente.
-- A partir de 2026 a fonte e o documento da NC: cada celula vem nos lados
-- ORIGEM e DESTINO com o mesmo valor; fica o DESTINO, que traz fonte, natureza
-- e UG responsavel detalhadas (a ORIGEM das enviadas vem generica: fonte
-- 1000000000, natureza 339000). Programa e acao vem do PTRES.
-- valor_celula e sempre positivo (o sentido esta no tipo, nc_evento_descricao);
-- movimento_liquido_moeda_origem tem o sinal do ponto de vista do MIR.
with

    ptres_programa as (
        select distinct on (ptres)
            ptres,
            programa_governo,
            programa_governo_descricao,
            acao_governo,
            acao_governo_descricao
        from {{ source("siafi", "programacao_acao_ptres") }}
        order by ptres asc, dt_ingest desc
    ),

    ate_2025 as (
        select
            programa_governo,
            programa_governo_descricao,
            acao_governo,
            acao_governo_descricao,
            nc,
            relatorio,
            left(nc, 6) as ug_emitente,
            null::text as ug_emitente_descricao,
            nc_transferencia,
            fonte_recursos as nc_fonte_recursos,
            fonte_recursos_descricao as nc_fonte_recursos_descricao,
            ptres,
            ug_responsavel as nc_ug_responsavel,
            ug_responsavel_descricao as nc_ug_responsavel_descricao,
            natureza_despesa as nc_natureza_despesa,
            natureza_despesa_descricao as nc_natureza_despesa_descricao,
            plano_interno as nc_plano_interno,
            plano_interno_descricao as nc_plano_interno_descricao1,
            favorecido_doc,
            favorecido_doc_descricao,
            favorecido_municipio,
            favorecido_municipio_descricao,
            {{ parse_financial_value("movimento_liquido_moeda_origem") }}
            as movimento_liquido_moeda_origem,
            null::text as descricao,
            null::date as emissao_dia,
            null::text as dc,
            (dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siafi", "nc_tesouro_ate_2025") }}
    ),

    desde_2026 as (
        select
            p.programa_governo,
            p.programa_governo_descricao,
            p.acao_governo,
            p.acao_governo_descricao,
            t.nc,
            t.relatorio,
            t.emitente_codigo as ug_emitente,
            t.emitente_nome as ug_emitente_descricao,
            t.nc_transferencia,
            t.fonte_codigo as nc_fonte_recursos,
            t.fonte_nome as nc_fonte_recursos_descricao,
            t.ptres,
            t.tipo_nc as nc_evento_descricao,
            t.ugr_codigo as nc_ug_responsavel,
            t.ugr_nome as nc_ug_responsavel_descricao,
            t.natureza_codigo as nc_natureza_despesa,
            t.natureza_nome as nc_natureza_despesa_descricao,
            t.pi_codigo as nc_plano_interno,
            t.pi_nome as nc_plano_interno_descricao1,
            t.favorecido_codigo as favorecido_doc,
            t.favorecido_nome as favorecido_doc_descricao,
            null::text as favorecido_municipio,
            null::text as favorecido_municipio_descricao,
            {{ parse_financial_value("t.valor_celula") }} as valor_celula,
            t.descricao,
            to_date(t.emissao_dia, 'DD/MM/YYYY') as emissao_dia,
            t.dc,
            (t.dt_ingest || '-03:00')::timestamptz as dt_ingest
        from {{ source("siafi", "nc_tesouro_desde_2026") }} as t
        left join ptres_programa as p on t.ptres = p.ptres
        where t.dc = 'DESTINO'
    )

select
    programa_governo,
    programa_governo_descricao,
    acao_governo,
    acao_governo_descricao,
    nc,
    relatorio,
    ug_emitente,
    ug_emitente_descricao,
    nc_transferencia,
    nc_fonte_recursos,
    nc_fonte_recursos_descricao,
    ptres,
    case
        when relatorio = 'enviadas' and movimento_liquido_moeda_origem > 0
        then 'DESCENTRALIZACAO DE CREDITO'
        when relatorio = 'enviadas'
        then 'ANULACAO DE DESCENTRALIZACAO DE CREDITO'
        when movimento_liquido_moeda_origem > 0
        then 'DESCENTRALIZACAO DE CREDITO'
        else 'DEVOLUCAO DE DESCENTRALIZACAO DE CREDITO'
    end as nc_evento_descricao,
    nc_ug_responsavel,
    nc_ug_responsavel_descricao,
    nc_natureza_despesa,
    nc_natureza_despesa_descricao,
    nc_plano_interno,
    nc_plano_interno_descricao1,
    favorecido_doc,
    favorecido_doc_descricao,
    favorecido_municipio,
    favorecido_municipio_descricao,
    abs(movimento_liquido_moeda_origem) as valor_celula,
    movimento_liquido_moeda_origem,
    descricao,
    emissao_dia,
    substring(nc from 12 for 4) as emissao_ano,
    dc,
    dt_ingest
from ate_2025

union all

select
    programa_governo,
    programa_governo_descricao,
    acao_governo,
    acao_governo_descricao,
    nc,
    relatorio,
    ug_emitente,
    ug_emitente_descricao,
    nc_transferencia,
    nc_fonte_recursos,
    nc_fonte_recursos_descricao,
    ptres,
    nc_evento_descricao,
    nc_ug_responsavel,
    nc_ug_responsavel_descricao,
    nc_natureza_despesa,
    nc_natureza_despesa_descricao,
    nc_plano_interno,
    nc_plano_interno_descricao1,
    favorecido_doc,
    favorecido_doc_descricao,
    favorecido_municipio,
    favorecido_municipio_descricao,
    valor_celula,
    case
        when nc_evento_descricao ~* '^DESC' then valor_celula else -valor_celula
    end as movimento_liquido_moeda_origem,
    descricao,
    emissao_dia,
    substring(nc from 12 for 4) as emissao_ano,
    dc,
    dt_ingest
from desde_2026
