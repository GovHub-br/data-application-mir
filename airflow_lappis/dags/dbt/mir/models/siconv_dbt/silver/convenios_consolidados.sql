{{ config(materialized="table") }}

with
    convenio as (
        select *
        from {{ ref("convenio") }}
    ),
    ppa_tesouro as (
        select *
        from {{ ref("ppa_tesouro") }}
        where ne_ccor <> '-9'
    ),
    convenios_ppa as (
        select
            cc.*,
            et.ug_responsavel_codigo,
            et.ug_responsavel_nome,
            et.programa_governo,
            et.programa_governo_descricao,
            et.acao_governo,
            et.acao_governo_descricao
        from convenio cc
        right join ppa_tesouro et
            on cc.nr_convenio = et.ne_info_complementar
        where cc.nr_convenio is not null
            and left(et.ne_ccor, 6) = '810008'
    ),
    convenios_consolidado as (
        select
            *,
            round((vl_desembolsado_conv / nullif(vl_global_conv, 0) * 100)::numeric, 1) as percentual_executado,
            round(((vl_global_conv - vl_desembolsado_conv) / nullif(vl_global_conv, 0) * 100)::numeric, 1) as percentual_faltante,
            cast(null as text) as ug_responsavel_codigo,
            cast(null as text) as ug_responsavel_nome
        from convenio
        where ug_emitente = 810008
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
            ug_responsavel_nome
        from convenios_ppa
    )

select *
from convenios_consolidado
