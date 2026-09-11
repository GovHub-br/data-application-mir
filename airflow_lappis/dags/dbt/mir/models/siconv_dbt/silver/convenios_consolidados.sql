{{ config(materialized="table") }}

with
    convenio as (
        select *
        from {{ ref("convenio") }}
    ),
    -- UGs responsaveis consolidadas em UM registro por convenio. ppa_tesouro
    -- esta no grao do empenho: um mesmo convenio pode ter empenhos em varias
    -- UGs. Concatenamos as UGs (string_agg) em vez de deixa-las na chave para
    -- nao multiplicar a linha do convenio no join abaixo — cada UG a mais
    -- repetiria todos os valores do convenio e inflaria as somas no resumo.
    ugs_por_convenio as (
        select
            ne_info_complementar as nr_convenio,
            string_agg(
                distinct cast(ug_responsavel_codigo as text),
                ', '
                order by cast(ug_responsavel_codigo as text)
            ) as ug_responsavel_codigo,
            string_agg(
                distinct ug_responsavel_nome, ', ' order by ug_responsavel_nome
            ) as ug_responsavel_nome,
            count(distinct ug_responsavel_codigo) as qtd_ugs_responsaveis
        from {{ ref("ppa_tesouro") }}
        where ne_ccor <> '-9'
            and left(ne_ccor, 6) = '810008'
            and ne_info_complementar is not null
        group by ne_info_complementar
    ),
    convenios_ppa as (
        select
            cc.*,
            u.ug_responsavel_codigo,
            u.ug_responsavel_nome,
            u.qtd_ugs_responsaveis
        from convenio cc
        inner join ugs_por_convenio u
            on cc.nr_convenio = u.nr_convenio
    ),
    convenios_consolidado as (
        select
            *,
            round((vl_desembolsado_conv / nullif(vl_global_conv, 0) * 100)::numeric, 1) as percentual_executado,
            round(((vl_global_conv - vl_desembolsado_conv) / nullif(vl_global_conv, 0) * 100)::numeric, 1) as percentual_faltante,
            cast(null as text) as ug_responsavel_codigo,
            cast(null as text) as ug_responsavel_nome,
            0 as qtd_ugs_responsaveis
        from convenio
        where ug_emitente = 810008
            and nr_convenio not in (select nr_convenio from convenios_ppa)
        union distinct
        select
            nr_convenio,
            id_proposta,
            dia,
            mes,
            ano,
            dia_assin_conv,
            sit_convenio,
            subsituacao_conv,
            situacao_publicacao,
            instrumento_ativo,
            ind_opera_obtv,
            nr_processo,
            ug_emitente,
            dia_publ_conv,
            dia_inic_vigenc_conv,
            dia_fim_vigenc_conv,
            dia_fim_vigenc_original_conv,
            dias_prest_contas,
            dia_limite_prest_contas,
            data_suspensiva,
            data_retirada_suspensiva,
            dias_clausula_suspensiva,
            situacao_contratacao,
            ind_assinado,
            motivo_suspensao,
            ind_foto,
            qtde_convenios,
            qtd_ta,
            qtd_prorroga,
            vl_global_conv,
            vl_repasse_conv,
            vl_contrapartida_conv,
            vl_empenhado_conv,
            vl_desembolsado_conv,
            vl_saldo_reman_tesouro,
            vl_saldo_reman_convenente,
            vl_rendimento_aplicacao,
            vl_ingresso_contrapartida,
            vl_saldo_conta,
            valor_global_original_conv,
            round((vl_desembolsado_conv / nullif(vl_global_conv, 0) * 100)::numeric, 1) as percentual_executado,
            round(((vl_global_conv - vl_desembolsado_conv) / nullif(vl_global_conv, 0) * 100)::numeric, 1) as percentual_faltante,
            ug_responsavel_codigo,
            ug_responsavel_nome,
            qtd_ugs_responsaveis
        from convenios_ppa
    )

select *
from convenios_consolidado
