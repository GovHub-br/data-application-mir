{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, Blocos 1 e 2 do formulário de convênios: um registro por
  convênio, contrato de repasse, termo de fomento ou termo de colaboração do MIR, com os
  campos que o formulário preenche sozinho. Fonte: siconv (Transferegov, discricionárias
  e legais).

  Universo: propostas do órgão superior 67000 (MIR) nessas quatro modalidades, já
  assinadas, menos as anuladas e canceladas. Das assinadas antes de 2023 entram só as que
  ainda não têm prestação de contas encerrada (concluída, aprovada ou rejeitada): em
  execução, aguardando ou com prestação de contas em análise. As parcerias do MROSC (Lei
  13.019/2014: termo de fomento e de colaboração) usam o mesmo formulário dos convênios e
  as mesmas tabelas do siconv, com os mesmos nomes de situação; o recorte é o mesmo.
  Termo de parceria (OSCIP, Lei 9.790/1999) fica fora.

  Lê as bronzes do siconv direto, sem passar por convenios_consolidados ou
  resumo_convenios, que filtram pela UG 810008 e não pela modalidade.

  Os valores (repasse, contrapartida, global) e o fim da vigência são os vigentes, já
  com os aditivos. O global inclui o rendimento de aplicação que o convenente foi
  autorizado a usar. O desembolsado está em coleta_convenio_execucao.

  cd_programa_ppa é o programa do PPA do item 3.1, pelas NEs do convênio no relatório
  de execução do PPA (ppa_tesouro), com a regra de coleta_ted. Não vem de
  coleta_convenio_fonte, que lê este modelo: referenciá-lo fecharia um ciclo no DAG.
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
            and p.modalidade in (
                'CONVENIO',
                'CONTRATO DE REPASSE',
                'TERMO DE FOMENTO',
                'TERMO DE COLABORACAO'
            )
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
    -- "4/2023" e "2/2026" assinado em 2025. Número fora do padrão "N/AAAA" fica por
    -- último, em vez de derrubar o build no cast.
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
                    case
                        when split_part(numero_ta, '/', 2) ~ '^[0-9]+$'
                        then split_part(numero_ta, '/', 2)::integer
                    end desc nulls last,
                    case
                        when split_part(numero_ta, '/', 1) ~ '^-?[0-9]+$'
                        then split_part(numero_ta, '/', 1)::integer
                    end desc nulls last
            ) as ordem
        from {{ ref("termo_aditivo") }}
        where nr_convenio in (select nr_convenio from convenio)
    ),

    -- Unidade concedente: a secretaria que aparece como UG responsável nos empenhos,
    -- pela UG própria dela (cd_ug_secretaria do seed). Os empenhos são emitidos pela UG
    -- 810008 (ou pela 238012, nos antigos); a secretaria só aparece na UG responsável.
    -- Sem secretaria, ou com mais de uma, fica o ministério.
    secretaria as (
        select e.nr_convenio, min(u.sg_unidade) as sg_unidade
        from {{ ref("empenho") }} as e
        inner join
            {{ ref("coleta_unidade_mir") }} as u
            on u.cd_ug_secretaria = e.ug_responsavel::text
        group by e.nr_convenio
        having count(distinct u.sg_unidade) = 1
    ),

    -- UG concedente: a que emite os empenhos, como no TED a UG descentralizadora é a
    -- que emite as NCs. Hoje cada convênio tem uma só (810008, ou 238012 nos antigos);
    -- com mais de uma, fica a de maior valor empenhado.
    emitente as (
        select distinct
            on (e.nr_convenio) e.nr_convenio, e.ug_emitente::text as cd_ug
        from {{ ref("empenho") }} as e
        where e.nr_convenio in (select nr_convenio from convenio)
        group by e.nr_convenio, e.ug_emitente
        order by e.nr_convenio, sum(e.valor_empenho) desc, e.ug_emitente::text
    ),

    -- Programas do PPA que a revisão vigente traz, para preferir o programa atual ao do
    -- PPA anterior (5034, nos empenhos até 2023).
    programa_vigente as (
        select distinct codigo
        from {{ ref("coleta_lista_ppa") }}
        where nivel = 'programa' and in_vigente
    ),

    -- Empenho de cada convênio por programa, pelas NEs que o siconv lista, procuradas no
    -- relatório do PPA pela NE completa (UG, gestão e número).
    programa_empenho as (
        select
            e.nr_convenio,
            t.programa_governo as cd_programa,
            max(t.ne_ccor_ano_emissao::integer) as aa_emissao,
            sum(t.despesas_empenhadas) as vl_liquido
        from {{ ref("empenho") }} as e
        inner join
            {{ ref("ppa_tesouro") }} as t
            on t.ne_ccor = lpad(e.ug_emitente::text, 6, '0') || '00001' || e.nr_empenho
        where
            e.nr_convenio in (select nr_convenio from convenio)
            and t.programa_governo is not null
        group by e.nr_convenio, t.programa_governo
    ),

    -- Um programa por convênio, como em coleta_ted: vigente primeiro, depois os com
    -- valor empenhado, em seguida o maior valor, depois o ano mais recente; o código
    -- desempata por último para o valor não depender da ordem.
    programa as (
        select distinct
            on (c.nr_convenio)
            c.nr_convenio,
            c.cd_programa,
            v.codigo is not null as in_vigente
        from programa_empenho as c
        left join programa_vigente as v on v.codigo = c.cd_programa
        order by
            c.nr_convenio,
            (v.codigo is not null) desc,
            (c.vl_liquido > 0) desc,
            c.vl_liquido desc nulls last,
            c.aa_emissao desc,
            c.cd_programa
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
    coalesce(g.cd_ug, u.cd_ug)::text as cd_ug_concedente,
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
    p.dt_posicao::date as dt_posicao,
    coalesce(c.vl_rendimento_aplicacao, 0)::numeric(15, 2) as vl_rendimento_aplicacao,
    pg.cd_programa::text as cd_programa_ppa,
    pg.in_vigente::boolean as in_programa_ppa_vigente,
    -- Opções do formulário do convenente. Inadimplente e as prestações de contas já
    -- encerradas não têm opção e ficam nulas (test_coleta_convenio_situacao_sem_opcao).
    case
        when
            c.sit_convenio in (
                'Proposta/Plano de Trabalho Aprovado',
                'Proposta/Plano de Trabalho Complementado Enviado para Análise',
                'Assinado',
                'Assinatura Pendente Registro TV Siafi'
            )
        then 'Plano de trabalho aprovado, sem início da execução'
        when c.sit_convenio = 'Em execução'
        then 'Em execução'
        when
            c.sit_convenio in (
                'Aguardando Prestação de Contas',
                'Prestação de Contas enviada para Análise',
                'Prestação de Contas em Análise',
                'Prestação de Contas Comprovada em Análise',
                'Prestação de Contas em Complementação',
                'Prestação de Contas Iniciada Por Antecipação'
            )
        then 'Execução concluída, em prestação de contas'
        when c.sit_convenio = 'Convênio Rescindido'
        then 'Extinta / rescindida'
    end::text as tp_situacao_execucao
from convenio as c
left join aditivo as a on a.nr_convenio = c.nr_convenio and a.ordem = 1
left join secretaria as s on s.nr_convenio = c.nr_convenio
left join emitente as g on g.nr_convenio = c.nr_convenio
-- Left join: se a linha do MIR sumir do seed, o not_null do contrato derruba o build em
-- vez de o convênio sumir da tabela.
left join
    {{ ref("coleta_unidade_mir") }} as u on u.sg_unidade = coalesce(s.sg_unidade, 'MIR')
left join {{ ref("justificativas_proposta") }} as j on j.id_proposta = c.id_proposta
left join programa as pg on pg.nr_convenio = c.nr_convenio
cross join posicao as p
