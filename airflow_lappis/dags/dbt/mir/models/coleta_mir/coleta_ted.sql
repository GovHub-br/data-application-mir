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

  Os valores executados (empenhado, liquidado, pago) entram depois, a partir de
  ted_execucao_por_instrumento.
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
    t.nr_processo_sei::text as nr_processo_sei,
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
    b.cd_siorg::text as cd_siorg_parceiro
from plano as p
left join {{ ref("programas_ted") }} as g on g.id_programa = p.id_programa
left join termo as t on t.id_plano_acao = p.id_plano_acao
left join beneficiario as b on b.id_programa = p.id_programa
