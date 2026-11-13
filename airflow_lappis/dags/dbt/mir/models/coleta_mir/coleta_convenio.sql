{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, Blocos 1 e 2 do formulário de convênios: um registro por
  convênio ou contrato de repasse do MIR, com os campos que o formulário preenche
  sozinho. Fonte: siconv (Transferegov, discricionárias e legais).

  Universo: propostas do órgão superior 67000 (MIR) nas modalidades CONVENIO e CONTRATO
  DE REPASSE, já assinadas, menos as anuladas e canceladas. Das assinadas antes de 2023
  entram só as que ainda não têm prestação de contas encerrada (concluída, aprovada ou
  rejeitada): em execução, aguardando ou com prestação de contas em análise. Termo de
  fomento, colaboração ou parceria (MROSC) fica fora: não é convênio no Decreto
  11.531/2023 e tem regime próprio.

  Lê as bronzes do siconv direto, sem passar por convenios_consolidados ou
  resumo_convenios, que filtram pela UG 810008 e não pela modalidade.

  Os valores (repasse, contrapartida, global) e o fim da vigência são os vigentes, já
  com os aditivos. O desembolsado está em coleta_convenio_execucao.
#}
with
    convenio as (
        select
            c.*,
            p.modalidade,
            p.objeto_proposta,
            p.identif_proponente,
            p.nm_proponente,
            p.natureza_juridica,
            p.uf_proponente,
            p.cod_munic_ibge,
            p.munic_proponente
        from {{ ref("convenio") }} as c
        inner join {{ ref("proposta") }} as p on p.id_proposta = c.id_proposta
        where
            p.cod_orgao_sup = 67000
            and p.modalidade in ('CONVENIO', 'CONTRATO DE REPASSE')
            and c.dia_assin_conv is not null
            and c.sit_convenio not in ('Convênio Anulado', 'Cancelado')
            and (
                c.dia_assin_conv >= '2023-01-01'
                or c.sit_convenio not in (
                    'Prestação de Contas Concluída',
                    'Prestação de Contas Aprovada',
                    'Prestação de Contas Aprovada com Ressalvas',
                    'Prestação de Contas Rejeitada'
                )
            )
    ),

    -- Último aditivo: pela data de assinatura e, no mesmo dia, pelo ano e número do TA
    -- como inteiros. O número sozinho não ordena: há "3/2023" assinado depois de
    -- "4/2023" e "2/2026" assinado em 2025.
    aditivo as (
        select
            nr_convenio,
            count(*) over (partition by nr_convenio) as qt_aditivos,
            numero_ta,
            dt_assinatura_ta,
            row_number() over (
                partition by nr_convenio
                order by
                    dt_assinatura_ta desc nulls last,
                    nullif(split_part(numero_ta, '/', 2), '')::integer desc nulls last,
                    nullif(split_part(numero_ta, '/', 1), '')::integer desc nulls last
            ) as ordem
        from {{ ref("termo_aditivo") }}
        where nr_convenio in (select nr_convenio from convenio)
    ),

    -- Unidade concedente: a secretaria que aparece como UG responsável nos empenhos.
    -- Os empenhos são emitidos pela UG 810008 (ou pela 238012, nos antigos); a
    -- secretaria só aparece na UG responsável. Sem secretaria, ou com mais de uma, fica
    -- o ministério.
    secretaria as (
        select e.nr_convenio, min(u.sg_unidade) as sg_unidade
        from {{ ref("empenho") }} as e
        inner join
            {{ ref("coleta_unidade_mir") }} as u
            on u.cd_ug = e.ug_responsavel::text
            and u.cd_ug <> '810008'
        group by e.nr_convenio
        having count(distinct u.sg_unidade) = 1
    ),

    -- Data do último evento do siconv no país inteiro: aproxima a data do retrato, já
    -- que as bronzes do siconv não têm data de carga.
    posicao as (
        select max(dia_historico_sit) as dt_posicao
        from {{ ref("historico_situacao") }}
    )

select
    c.nr_convenio::text as nr_convenio,
    c.id_proposta::integer as id_proposta,
    c.modalidade::text as tp_instrumento,
    case
        when c.nr_processo ~ '^[0-9]{17}$'
        then
            substr(c.nr_processo, 1, 5)
            || '.'
            || substr(c.nr_processo, 6, 6)
            || '/'
            || substr(c.nr_processo, 12, 4)
            || '-'
            || substr(c.nr_processo, 16, 2)
        else nullif(trim(c.nr_processo), '')
    end::text as nr_processo,
    c.objeto_proposta::text as ds_objeto,
    c.dia_assin_conv::date as dt_assinatura,
    c.dia_publ_conv::date as dt_publicacao,
    c.dia_inic_vigenc_conv::date as dt_inicio_vigencia,
    c.dia_fim_vigenc_conv::date as dt_fim_vigencia,
    c.dia_fim_vigenc_original_conv::date as dt_fim_vigencia_original,
    coalesce(a.qt_aditivos, 0)::integer as qt_aditivos,
    a.numero_ta::text as nr_ultimo_aditivo,
    a.dt_assinatura_ta::date as dt_ultimo_aditivo,
    c.vl_repasse_conv::numeric(15, 2) as vl_repasse,
    c.vl_contrapartida_conv::numeric(15, 2) as vl_contrapartida,
    c.vl_global_conv::numeric(15, 2) as vl_global,
    c.sit_convenio::text as ds_situacao,
    nullif(trim(c.subsituacao_conv), '')::text as ds_subsituacao,
    c.dia_limite_prest_contas::date as dt_limite_prestacao_contas,
    u.sg_unidade::text as sg_unidade_concedente,
    u.no_unidade::text as no_unidade_concedente,
    u.cd_ug::text as cd_ug_concedente,
    c.identif_proponente::text as nr_cnpj_convenente,
    c.nm_proponente::text as no_convenente,
    c.natureza_juridica::text as ds_natureza_juridica,
    case
        when c.natureza_juridica = 'Administração Pública Municipal'
        then 'Administração pública municipal'
        when
            c.natureza_juridica
            = 'Administração Pública Estadual ou do Distrito Federal'
            and c.uf_proponente = 'DF'
        then 'Administração pública distrital'
        when
            c.natureza_juridica
            = 'Administração Pública Estadual ou do Distrito Federal'
        then 'Administração pública estadual'
        when c.natureza_juridica = 'Consórcio Público'
        then 'Consórcio público'
        when c.natureza_juridica = 'Organização da Sociedade Civil'
        then 'Entidade privada sem fins lucrativos'
    end::text as tp_natureza_convenente,
    c.uf_proponente::text as sg_uf_convenente,
    c.cod_munic_ibge::text as cd_municipio_convenente,
    c.munic_proponente::text as no_municipio_convenente,
    nullif(trim(j.justificativa), '')::text as ds_justificativa,
    nullif(trim(j.problema_a_ser_resolvido), '')::text as ds_problema,
    nullif(trim(j.resultados_esperados), '')::text as ds_resultados_esperados,
    nullif(trim(j.caracterizacao_interesses_reci), '')::text
    as ds_interesses_reciprocos,
    nullif(trim(j.publico_alvo), '')::text as ds_publico_alvo,
    p.dt_posicao::date as dt_posicao
from convenio as c
left join aditivo as a on a.nr_convenio = c.nr_convenio and a.ordem = 1
left join secretaria as s on s.nr_convenio = c.nr_convenio
inner join
    {{ ref("coleta_unidade_mir") }} as u on u.sg_unidade = coalesce(s.sg_unidade, 'MIR')
left join {{ ref("justificativas_proposta") }} as j on j.id_proposta = c.id_proposta
cross join posicao as p
