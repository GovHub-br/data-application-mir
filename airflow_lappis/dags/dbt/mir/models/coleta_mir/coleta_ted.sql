{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, Blocos 1 e 2 do formulário de TEDs: um registro por TED
  firmado do MIR, com os campos que o formulário preenche sozinho.

  Universo: planos de ação do portal TED que já têm número de transferência, menos os
  rejeitados. O portal é a fonte, e não a API de dados abertos, porque está mais em
  dia: em 21/10 ele já dava como aprovados, com número, 8 TEDs de 2026 que a API ainda
  não dava.

  cd_ted é o código do programa do TED (14 dígitos), o "Número do TED" do formulário.
  O programa vem da API de dados abertos, atrás do portal; sem ele, o número sai do
  código do plano no portal ("30882320220003-000328"). nr_transferencia é o número que
  as NCs e NEs do SIAFI citam. Hoje programa, plano e TED são 1 para 1 (constraints
  unique); a chave do contrato é id_plano_acao.

  Sem data de carga: o dt_ingest das bronzes lê como horário de Brasília um horário
  gravado em UTC. A coluna entra quando as bronzes forem corrigidas.

  nr_processo_sei sai do termo de execução e, quando o termo não traz, da página de
  transferências do MIR no gov.br; ds_origem_sei diz qual das duas preencheu.

  cd_programa_ppa é o programa do PPA do item 3.1, pelas NCs do TED. Não vem de
  coleta_ted_fonte, que seria a fonte natural: aquele modelo lê coleta_ted, e
  referenciá-lo aqui fecharia um ciclo no DAG. Deriva das mesmas NCs e reproduz o
  programa dele em todos os 100 TEDs em comum (conferido em 2026-11-11); fica sem os 5
  TEDs de 2022 que só têm nota na API de TED.

  Os valores executados (empenhado e pago) estão em coleta_ted_execucao.
#}
with
    plano as (
        select *
        from {{ ref("planos_acao_portal_ted") }}
        where
            sq_instrumento is not null
            and tx_situacao_plano_acao is distinct from 'REJEITADO'
    ),

    -- Termo que celebrou o TED: o primeiro assinado do plano.
    termo as (
        select distinct
            on (id_plano_acao)
            id_plano_acao,
            nr_processo_sei,
            dt_assinatura,
            ds_situacao
        from {{ ref("termos_execucao_ted") }}
        order by id_plano_acao, dt_assinatura, id_termo
    ),

    -- Siorg do parceiro: só quando o programa tem um beneficiário. Com mais de um,
    -- não há como saber qual é o do plano.
    beneficiario as (
        select id_programa, max(cd_siorg) as cd_siorg
        from {{ ref("programas_beneficiario_ted") }}
        group by id_programa
        having count(*) = 1
    ),

    -- Processo SEI da página do gov.br, para completar o que o termo não traz. Só pelo
    -- num_transf principal: pelos num_transf_alternativos o processo de um TED vai parar
    -- em outro. O having descarta o num_transf que a página traga com dois processos, em
    -- vez de escolher um ou duplicar a linha do TED (hoje não há nenhum).
    sei_gov_br as (
        select num_transf, max(processo) as nr_processo_sei
        from {{ ref("teds_gov_br") }}
        where num_transf is not null and processo is not null
        group by num_transf
        having count(distinct processo) = 1
    ),

    -- Programas do PPA que a revisão vigente traz, para preferir o programa atual do TED
    -- ao do PPA anterior (5034, nos TEDs de 2023).
    programa_vigente as (
        select distinct codigo
        from {{ ref("coleta_lista_ppa") }}
        where nivel = 'programa' and in_vigente
    ),

    -- Crédito do TED por programa, pelas NCs que citam o número da transferência. O
    -- sentido do evento é o mesmo de coleta_ted_fonte: só a descentralização soma.
    programa_credito as (
        select
            p.id_plano_acao,
            n.programa_governo as cd_programa,
            max(n.emissao_ano::integer) as aa_emissao,
            sum(
                case
                    when n.nc_evento_descricao = 'DESCENTRALIZACAO DE CREDITO'
                    then n.valor_celula
                    else - n.valor_celula
                end
            ) as vl_liquido
        from plano as p
        join {{ ref("nc_unificado") }} as n on n.nc_transferencia = p.sq_instrumento::text
        where n.programa_governo is not null
        group by p.id_plano_acao, n.programa_governo
    ),

    -- Um programa por TED: vigente primeiro, depois o do ano mais recente, depois o de
    -- maior crédito; o código desempata por último para o valor não depender da ordem.
    programa as (
        select distinct
            on (c.id_plano_acao)
            c.id_plano_acao,
            c.cd_programa,
            v.codigo is not null as in_vigente
        from programa_credito as c
        left join programa_vigente as v on v.codigo = c.cd_programa
        order by
            c.id_plano_acao,
            (v.codigo is not null) desc,
            c.aa_emissao desc,
            c.vl_liquido desc nulls last,
            c.cd_programa
    )

select
    p.id_plano_acao::integer as id_plano_acao,
    coalesce(g.tx_codigo_programa, split_part(p.codigo_plano_acao, '-', 1))::text
    as cd_ted,
    g.tx_nome_programa::text as no_ted,
    p.sq_instrumento::text as nr_transferencia,
    p.aa_instrumento::integer as aa_instrumento,
    p.tx_situacao_plano_acao::text as ds_situacao_plano,
    t.ds_situacao::text as ds_situacao_termo,
    coalesce(t.nr_processo_sei, s.nr_processo_sei)::text as nr_processo_sei,
    t.dt_assinatura::date as dt_assinatura,
    p.tx_objeto_plano_acao::text as ds_objeto,
    p.tx_justificativa_plano_acao::text as ds_justificativa,
    p.vl_total_plano_acao::numeric(15, 2) as vl_total,
    p.dt_inicio_vigencia::date as dt_inicio_vigencia,
    p.dt_fim_vigencia::date as dt_fim_vigencia,
    p.sigla_unidade_responsavel_acompanhamento::text as sg_unidade_acompanhamento,
    p.unidade_responsavel_acompanhamento::text as no_unidade_acompanhamento,
    p.sigla_unidade_descentralizada::text as sg_parceiro,
    p.unidade_descentralizada::text as no_parceiro,
    p.cd_ug_unidade_descentralizada::text as cd_ug_parceiro,
    b.cd_siorg::text as cd_siorg_parceiro,
    pg.cd_programa::text as cd_programa_ppa,
    pg.in_vigente::boolean as in_programa_ppa_vigente,
    case
        when t.nr_processo_sei is not null
        then 'termo_ted'
        when s.nr_processo_sei is not null
        then 'gov_br'
    end::text as ds_origem_sei
from plano as p
left join {{ ref("programas_ted") }} as g on g.id_programa = p.id_programa
left join termo as t on t.id_plano_acao = p.id_plano_acao
left join beneficiario as b on b.id_programa = p.id_programa
left join sei_gov_br as s on s.num_transf = p.sq_instrumento::text
left join programa as pg on pg.id_plano_acao = p.id_plano_acao
