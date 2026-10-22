{{ config(materialized="table") }}

-- Contrato do Coleta MIR: um registro por instrumento. Ver schema.yml e o
-- documento de desenho do Coleta MIR (secao 7.1) antes de mudar colunas.
with
    plano as (
        select
            id_plano_acao::text as id_plano_acao,
            nullif(
                regexp_replace(cd_ug_unidade_descentralizada::text, '\D', '', 'g'), ''
            ) as ug_plano,
            unidade_descentralizada::text as unidade_descentralizada,
            tx_objeto_plano_acao::text as tx_objeto_plano_acao
        from {{ ref("ted_plano_acao_consolidado") }}
    ),

    -- Termo de execucao mais recente do plano: processo SEI e data de
    -- assinatura do TED (Bloco 1).
    termo as (
        select distinct
            on (id_plano_acao)
            id_plano_acao::text as id_plano_acao,
            nr_processo_sei,
            dt_assinatura
        from {{ ref("termos_execucao_ted") }}
        order by id_plano_acao, dt_assinatura desc nulls last, id_termo desc
    ),

    -- Tedinho: so entram os identificados nas paginas de transparencia do
    -- gov.br, lidos direto do modelo da pagina (ted_tedinho_gov_br: uma linha
    -- por instrumento da pagina, com processo, parceiro e objeto). Nao usa
    -- ted_execucao_por_instrumento, que vem da reconciliacao das NEs e tem
    -- tedinhos sem evidencia da pagina.
    -- Na pagina o instrumento e 'tedinho <NC>' ou mesclado ('tedinho <A> / <B>',
    -- 'tedinho <A> + tedinho <B>'): abre em NCs.
    tedinho_pagina_nc as (
        select
            pg.instrumento,
            pg.processo,
            pg.parceiro,
            pg.objeto,
            partes.nc,
            cardinality(
                regexp_split_to_array(replace(pg.instrumento, 'tedinho ', ''), ' (/|\+) ')
            ) as qt_partes
        from {{ ref("ted_tedinho_gov_br") }} as pg
        cross join
            lateral unnest(
                regexp_split_to_array(replace(pg.instrumento, 'tedinho ', ''), ' (/|\+) ')
            ) as partes(nc)
    ),

    -- NC -> instrumento_key de tedinhos_mir (= id_instrumento do tedinho no
    -- resumo: 'nc:', 'proc:' ou 'transf:'). tedinhos_mir tem uma linha por
    -- celula da NC, mas cada NC tem um unico instrumento_key (conferido).
    tedinho_nc_chave as (
        select nc, instrumento_key::text as chave
        from {{ ref("tedinhos_mir") }}
        group by nc, instrumento_key
    ),

    -- Uma linha por chave. Desempate deterministico: com parceiro, depois o
    -- instrumento da pagina menos mesclado, depois a menor NC.
    tedinho_info_chave as (
        select distinct
            on (k.chave) k.chave, p.parceiro, p.objeto, p.processo as processo_gov_br
        from tedinho_pagina_nc as p
        join tedinho_nc_chave as k on k.nc = p.nc
        order by k.chave, p.parceiro is null, p.qt_partes, p.nc, p.instrumento
    ),

    -- Menor NC de cada instrumento de tedinho: referencia estavel para o
    -- consumidor religar o instrumento se o nr_instrumento mudar.
    tedinho_nc_referencia as (
        select chave, min(nc) as nc_referencia from tedinho_nc_chave group by chave
    ),

    -- MIR: UGs do proprio ministerio (seed ugs_mir). Nunca sao parceiro.
    mir as (select ug_codigo::text as ug_codigo from {{ ref("ugs_mir") }}),

    -- UG que recebeu o credito do TED (ted_credito_instrumento), so quando as
    -- notas de credito do TED apontam uma UG unica fora do MIR. A chave e o
    -- num_transf sem zeros a esquerda, igual ao id_instrumento do TED.
    ted_ug_credito as (
        select ltrim(num_transf, '0') as id_instrumento, min(ug) as ug_credito
        from {{ ref("ted_credito_instrumento") }}
        where ug ~ '^\d{6}$' and ug not in (select ug_codigo from mir)
        group by ltrim(num_transf, '0')
        having count(distinct ug) = 1
    ),

    -- UG favorecida das notas de credito do tedinho (tedinhos_mir x
    -- nc_tesouro_mir), so quando e uma unica UG fora do MIR. Agregado a uma
    -- linha por instrumento_key (= id_instrumento do tedinho) antes do join.
    tedinho_ug_credito as (
        select tm.instrumento_key as id_instrumento, min(n.favorecido_doc) as ug_credito
        from {{ ref("tedinhos_mir") }} as tm
        join {{ ref("nc_tesouro_mir") }} as n on n.nc = tm.nc
        where
            tm.tedinho_provavel
            and n.favorecido_doc ~ '^\d{6}$'
            and n.favorecido_doc not in (select ug_codigo from mir)
        group by tm.instrumento_key
        having count(distinct n.favorecido_doc) = 1
    ),

    -- UG unica do empenho (ted_resumo_orcamentario.ugs_responsaveis_codigos),
    -- so quando qtd_ugs_responsaveis = 1, 6 digitos e fora do MIR.
    ted_ug_empenho as (
        select
            r.id_instrumento::text as id_instrumento,
            r.ugs_responsaveis_codigos::text as ug_empenho
        from {{ ref("ted_resumo_orcamentario") }} as r
        where
            r.tipo_instrumento = 'TED'
            and r.qtd_ugs_responsaveis = 1
            and r.ugs_responsaveis_codigos::text ~ '^\d{6}$'
            and r.ugs_responsaveis_codigos::text not in (select ug_codigo from mir)
    ),

    teds as (
        select
            case
                r.tipo_instrumento when 'TED' then 'ted' else 'tedinho'
            end as tp_instrumento,
            r.id_instrumento::text as nr_instrumento,
            nr.nc_referencia,
            -- UG do parceiro. TED, em ordem: UG do plano no portal; UG que
            -- recebeu o credito (ted_ug_credito); UG unica do empenho
            -- (ted_ug_empenho). A UG do plano so vale com 6 digitos e fora do
            -- MIR (ex.: plano 245 traz '26350', codigo de orgao). Tedinho: a UG
            -- favorecida das notas de credito (tedinho_ug_credito). UG do MIR
            -- nunca entra.
            coalesce(
                case
                    when
                        p.ug_plano ~ '^\d{6}$'
                        and p.ug_plano not in (select ug_codigo from mir)
                    then p.ug_plano
                end,
                uc.ug_credito,
                ue.ug_empenho,
                tu.ug_credito
            ) as co_identificador,
            coalesce(
                p.unidade_descentralizada,
                r.sigla_unidade_descentralizada::text,
                t.parceiro
            ) as no_parceiro,
            coalesce(p.tx_objeto_plano_acao, t.objeto) as ds_objeto,
            r.valor_firmado::numeric as vl_firmado,
            r.empenhado::numeric as vl_empenhado,
            r.despesas_liquidada::numeric as vl_liquidado,
            (
                coalesce(r.despesas_pagas_exercicio, 0)
                + coalesce(r.despesas_pagas_rap, 0)
            )::numeric as vl_pago,
            r.dt_inicio_vigencia::date as dt_inicio_vigencia,
            r.dt_fim_vigencia::date as dt_fim_vigencia,
            tm.dt_assinatura,
            r.situacao_plano_acao::text as ds_situacao,
            -- Processo SEI: do termo de execucao (TED) ou da pagina do gov.br
            -- (tedinho). r.processo so vale no formato SEI: no tedinho 'nc:' ele
            -- traz o numero da NC, que nao e processo.
            coalesce(
                tm.nr_processo_sei,
                t.processo_gov_br,
                case
                    when r.processo::text ~ '^\d{5}\.\d{6}/\d{4}-\d{2}$'
                    then r.processo::text
                end
            ) as nr_processo_sei,
            cast(null as integer) as qt_aditivos,
            r.dt_ingest::timestamptz as dt_ingest
        from {{ ref("ted_resumo_orcamentario") }} as r
        left join plano as p on p.id_plano_acao = r.plano_acao::text
        left join termo as tm on tm.id_plano_acao = r.plano_acao::text
        left join
            tedinho_info_chave as t
            on r.tipo_instrumento = 'Tedinho'
            and t.chave = r.id_instrumento::text
        left join
            ted_ug_credito as uc
            on r.tipo_instrumento = 'TED'
            and uc.id_instrumento = r.id_instrumento::text
        left join ted_ug_empenho as ue on ue.id_instrumento = r.id_instrumento::text
        left join
            tedinho_nc_referencia as nr
            on r.tipo_instrumento = 'Tedinho'
            and nr.chave = r.id_instrumento::text
        left join
            tedinho_ug_credito as tu
            on r.tipo_instrumento = 'Tedinho'
            and tu.id_instrumento = r.id_instrumento::text
        -- Tedinho so entra no contrato quando foi identificado nas paginas de
        -- transparencia do gov.br (casou com tedinho_info_chave, que vem de
        -- ted_tedinho_gov_br).
        where r.tipo_instrumento = 'TED' or t.chave is not null
    ),

    proponente as (
        select
            cc.nr_convenio::text as nr_convenio,
            pr.identif_proponente::text as identif_proponente,
            cc.nr_processo::text as nr_processo
        from {{ ref("convenios_consolidados") }} as cc
        left join {{ ref("proposta") }} as pr on pr.id_proposta = cc.id_proposta
    ),

    -- Termo de fomento tem tabela propria; se o mesmo nr_convenio aparecer nas
    -- duas, vale resumo_termos_fomento (prioridade 1).
    convenio_origem as (
        select
            1 as prioridade,
            'termo_fomento' as tp_instrumento,
            nr_convenio,
            nome_convenente,
            objeto,
            valor_firmado_atualizado,
            valor_empenhado,
            valor_total_pago,
            inicio_vigencia,
            fim_vigencia,
            data_assinatura,
            situacao_atual,
            quantidade_aditivos
        from {{ ref("resumo_termos_fomento") }}
        union all
        select
            2 as prioridade,
            case
                when upper(modalidade_instrumento::text) like '%FOMENTO%'
                then 'termo_fomento'
                else 'convenio'
            end as tp_instrumento,
            nr_convenio,
            nome_convenente,
            objeto,
            valor_firmado_atualizado,
            valor_empenhado,
            valor_total_pago,
            inicio_vigencia,
            fim_vigencia,
            data_assinatura,
            situacao_atual,
            quantidade_aditivos
        from {{ ref("resumo_convenios") }}
    ),

    convenios as (
        select distinct
            on (c.nr_convenio::text)
            c.tp_instrumento,
            c.nr_convenio::text as nr_instrumento,
            cast(null as text) as nc_referencia,
            nullif(
                regexp_replace(pp.identif_proponente, '\D', '', 'g'), ''
            ) as co_identificador,
            c.nome_convenente::text as no_parceiro,
            c.objeto::text as ds_objeto,
            c.valor_firmado_atualizado::numeric as vl_firmado,
            c.valor_empenhado::numeric as vl_empenhado,
            cast(null as numeric) as vl_liquidado,
            c.valor_total_pago::numeric as vl_pago,
            c.inicio_vigencia::date as dt_inicio_vigencia,
            c.fim_vigencia::date as dt_fim_vigencia,
            c.data_assinatura::date as dt_assinatura,
            c.situacao_atual::text as ds_situacao,
            pp.nr_processo as nr_processo_sei,
            c.quantidade_aditivos::integer as qt_aditivos,
            -- os resumos do SICONV nao expoem dt_ingest; vale o momento do build
            now() as dt_ingest
        from convenio_origem as c
        left join proponente as pp on pp.nr_convenio = c.nr_convenio::text
        order by c.nr_convenio::text, c.prioridade
    ),

    unificado as (
        select
            tp_instrumento,
            nr_instrumento,
            nc_referencia,
            case when co_identificador is not null then 'ug' end as tp_identificador,
            co_identificador,
            no_parceiro,
            ds_objeto,
            vl_firmado,
            vl_empenhado,
            vl_liquidado,
            vl_pago,
            dt_inicio_vigencia,
            dt_fim_vigencia,
            dt_assinatura,
            ds_situacao,
            nr_processo_sei,
            qt_aditivos,
            dt_ingest
        from teds
        union all
        select
            tp_instrumento,
            nr_instrumento,
            nc_referencia,
            case when co_identificador is not null then 'cnpj' end as tp_identificador,
            co_identificador,
            no_parceiro,
            ds_objeto,
            vl_firmado,
            vl_empenhado,
            vl_liquidado,
            vl_pago,
            dt_inicio_vigencia,
            dt_fim_vigencia,
            dt_assinatura,
            ds_situacao,
            nr_processo_sei,
            qt_aditivos,
            dt_ingest
        from convenios
    )

select tp_instrumento || ':' || nr_instrumento as chave, *
from unificado
