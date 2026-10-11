{{ config(materialized="table") }}

-- Abertura de empenhos_por_plano_acao por exercicio da despesa (issue #510):
-- ted_resumo_orcamentario agrega cada TED numa unica linha, sem distinguir o
-- ano em que a despesa de fato ocorreu do ano do plano de acao (aa_ano_plano_acao,
-- que e quando o plano foi pactuado, nao quando foi executado). A CGPO compara
-- por exercicio; essa tabela expoe o grao (num_transf, exercicio) para que o
-- painel abra qualquer metrica de execucao por ano real da despesa, comparavel
-- com a planilha deles. So cobre TED -- tedinho nao tem join confiavel com
-- empenhos_por_plano_acao (ver tedinhos_mir e o comentario em
-- ted_resumo_orcamentario.sql sobre essa limitacao).
with

    plano_por_transf as (
        select num_transf_canon, plano_acao::integer as plano_acao
        from (
            select
                ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
                plano_acao,
                row_number() over (
                    partition by ltrim(trim(cast(num_transf as text)), '0')
                    order by plano_acao
                ) as rn
            from {{ ref("num_transf_n_plano_acao") }}
            where num_transf is not null
        ) t
        where rn = 1
    ),

    por_exercicio as (
        select
            ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
            ne_ccor_ano_emissao as exercicio,
            sum(
                case when despesas_empenhadas > 0 then despesas_empenhadas else 0 end
            ) as empenhado,
            sum(
                case when despesas_empenhadas < 0 then -despesas_empenhadas else 0 end
            ) as empenho_anulado,
            sum(despesas_pagas) as despesas_pagas_exercicio,
            sum(restos_a_pagar_pagos) as despesas_pagas_rap,
            sum(restos_a_pagar_inscritos) as restos_a_pagar,
            sum(despesas_liquidadas) as despesas_liquidada,
            max(dt_ingest) as dt_ingest
        from {{ ref("empenhos_por_plano_acao") }}
        where num_transf is not null
            and ltrim(trim(cast(num_transf as text)), '0') <> ''
            and ne_ccor_ano_emissao is not null
        group by
            ltrim(trim(cast(num_transf as text)), '0'), ne_ccor_ano_emissao
    )

select
    pe.num_transf_canon as num_transf,
    ppt.plano_acao,
    pe.exercicio,
    pe.empenhado,
    pe.empenho_anulado,
    pe.despesas_pagas_exercicio,
    pe.despesas_pagas_rap,
    pe.restos_a_pagar,
    pe.despesas_liquidada,
    pe.dt_ingest
from por_exercicio pe
left join plano_por_transf ppt using (num_transf_canon)
