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

    -- Parceiro, objeto e processo do tedinho vem da pagina do gov.br, exposta
    -- em ted_execucao_por_instrumento. La o instrumento e 'tedinho <NC>', ou
    -- mesclado ('tedinho <NC_A> / <NC_B>', 'tedinho <NC_A> + tedinho <NC_B>');
    -- aqui o id_instrumento do tedinho e 'nc:<NC>'. Abre o instrumento em NCs
    -- e fica com uma linha por NC, preferindo o instrumento com parceiro e o
    -- menos mesclado.
    tedinho_pagina as (
        select
            instrumento,
            max(parceiro) as parceiro,
            max(objeto) as objeto,
            max(processo_gov_br) as processo_gov_br
        from {{ ref("ted_execucao_por_instrumento") }}
        where tipo_instrumento = 'Tedinho'
        group by instrumento
    ),

    tedinho_info as (
        select distinct on (nc) nc, tp.parceiro, tp.objeto, tp.processo_gov_br
        from tedinho_pagina as tp
        cross join
            lateral unnest(
                regexp_split_to_array(replace(tp.instrumento, 'tedinho ', ''), ' (/|\+) ')
            ) as partes(nc)
        order by
            nc,
            tp.parceiro is null,
            cardinality(
                regexp_split_to_array(replace(tp.instrumento, 'tedinho ', ''), ' (/|\+) ')
            ),
            tp.instrumento
    ),

    teds as (
        select
            case
                r.tipo_instrumento when 'TED' then 'ted' else 'tedinho'
            end as tp_instrumento,
            r.id_instrumento::text as nr_instrumento,
            -- UG da unidade descentralizada: portal do TED; sem plano no portal,
            -- a UG que empenhou, quando e uma so (num TED quem empenha e quem
            -- recebeu o credito).
            coalesce(
                p.ug_plano,
                case
                    when r.qtd_ugs_responsaveis = 1
                    then
                        nullif(
                            regexp_replace(
                                r.ugs_responsaveis_codigos::text, '\D', '', 'g'
                            ),
                            ''
                        )
                end
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
            coalesce(
                tm.nr_processo_sei, r.processo::text, t.processo_gov_br
            ) as nr_processo_sei,
            cast(null as integer) as qt_aditivos,
            r.dt_ingest::timestamptz as dt_ingest
        from {{ ref("ted_resumo_orcamentario") }} as r
        left join plano as p on p.id_plano_acao = r.plano_acao::text
        left join termo as tm on tm.id_plano_acao = r.plano_acao::text
        left join
            tedinho_info as t
            on r.tipo_instrumento = 'Tedinho'
            and t.nc = regexp_replace(r.id_instrumento::text, '^nc:', '')
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
