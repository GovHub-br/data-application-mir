{{ config(materialized="table") }}

-- Universo de convenios do MIR no SICONV, no grao do instrumento. Mesmo
-- recorte de convenios_consolidados: ug_emitente 810008 ou com NE da UG 810008
-- vinculada no nucleo. A origem do recurso vem das NEs do nucleo (de qualquer
-- UG); sem NE, a origem nao e conhecida.
with
    nes as (
        select
            nr_instrumento as nr_convenio,
            ug_emitente_codigo,
            origem_recurso,
            ug_responsavel_codigo,
            ug_responsavel_nome
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'SICONV'
    ),

    recorte as (
        select nr_convenio
        from {{ ref("convenio") }}
        where ug_emitente = 810008

        union

        select nr_convenio
        from nes
        where ug_emitente_codigo = '810008'
    ),

    origem as (
        select
            nr_convenio,
            bool_or(origem_recurso = 'Emenda') as tem_emenda,
            bool_or(origem_recurso = 'Recurso próprio') as tem_proprio,
            string_agg(
                distinct ug_responsavel_codigo, ', ' order by ug_responsavel_codigo
            ) as ug_responsavel_codigo,
            string_agg(
                distinct ug_responsavel_nome, ', ' order by ug_responsavel_nome
            ) as ug_responsavel_nome
        from nes
        group by nr_convenio
    )

select
    c.nr_convenio,
    c.id_proposta,
    c.nr_processo,
    p.modalidade,
    p.objeto_proposta as objeto,

    -- Situacao
    c.sit_convenio as situacao,
    c.subsituacao_conv as subsituacao,
    c.situacao_publicacao,
    c.instrumento_ativo,
    c.ug_emitente::text as ug_emitente,

    -- Datas
    c.dia_assin_conv as data_assinatura,
    c.dia_publ_conv as data_publicacao,
    c.dia_inic_vigenc_conv as data_inicio_vigencia,
    c.dia_fim_vigenc_conv as data_fim_vigencia,
    c.dia_fim_vigenc_original_conv as data_fim_vigencia_original,
    c.dia_limite_prest_contas as data_limite_prestacao_contas,

    -- Valores pactuados
    c.valor_global_original_conv as valor_global_original,
    c.vl_global_conv as valor_global,
    c.vl_repasse_conv as valor_repasse,
    c.vl_contrapartida_conv as valor_contrapartida,
    c.vl_saldo_conta as valor_saldo_conta,

    -- Convenente e local de execucao
    regexp_replace(p.identif_proponente, '\D', '', 'g') as convenente_documento,
    p.nm_proponente as convenente_nome,
    p.natureza_juridica as convenente_natureza_juridica,
    p.uf_proponente as uf,
    p.munic_proponente as municipio,
    lpad(p.cod_munic_ibge::text, 7, '0') as cod_municipio_ibge,

    -- Origem do recurso
    case
        when o.tem_emenda
        then 'Emenda'
        when o.nr_convenio is not null
        then 'Recurso próprio'
        else 'Não identificada'
    end as origem_recurso,
    coalesce(o.tem_emenda and o.tem_proprio, false) as complemento_proprio,
    o.ug_responsavel_codigo,
    o.ug_responsavel_nome
from {{ ref("convenio") }} as c
inner join recorte as r on r.nr_convenio = c.nr_convenio
left join {{ ref("proposta") }} as p on p.id_proposta = c.id_proposta
left join origem as o on o.nr_convenio = c.nr_convenio
