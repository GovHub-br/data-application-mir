{{ config(materialized="table") }}

-- Planos de acao de TED do MIR (TransfereGov), uma linha por plano, com os
-- atributos do programa achatados. num_transf e o sq_instrumento: o numero da
-- transferencia no SIAFI, que liga NC, PF e NE ao plano. A origem do recurso
-- vem das NEs do nucleo (mesma regra de convenio_mir); sem NE, nao e conhecida.
with
    planos as (
        select distinct on (id_plano_acao) *
        from {{ ref("planos_acao_ted") }}
        order by id_plano_acao, dt_ingest desc
    ),

    programas as (
        select distinct on (id_programa) *
        from {{ ref("programas_ted") }}
        order by id_programa, dt_ingest desc
    ),

    origem as (
        select
            nr_instrumento::integer as id_plano_acao,
            bool_or(origem_recurso = 'Emenda') as tem_emenda,
            bool_or(origem_recurso = 'Recurso próprio') as tem_proprio
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'TED'
        group by nr_instrumento
    )

select
    p.id_plano_acao,
    i.num_transf,
    p.aa_instrumento as ano_instrumento,
    p.aa_ano_plano_acao as ano,
    p.tx_situacao_plano_acao as situacao,
    p.tx_objeto_plano_acao as objeto,
    p.tx_justificativa_plano_acao as justificativa,
    p.dt_inicio_vigencia as data_inicio_vigencia,
    p.dt_fim_vigencia as data_fim_vigencia,
    p.in_forma_execucao_direta as execucao_direta,
    p.in_forma_execucao_particulares as execucao_particulares,
    p.in_forma_execucao_descentralizada as execucao_descentralizada,
    p.sigla_unidade_descentralizada,
    p.unidade_descentralizada,
    p.sigla_unidade_responsavel_execucao,
    p.unidade_responsavel_execucao,
    p.vl_total_plano_acao as valor_firmado,
    p.vl_beneficiario_especifico as valor_beneficiario_especifico,
    p.vl_chamamento_publico as valor_chamamento_publico,

    -- Programa
    p.id_programa,
    g.tx_codigo_programa as codigo_programa,
    g.tx_nome_programa as nome_programa,
    g.aa_ano_programa as ano_programa,
    g.tx_situacao_programa as situacao_programa,
    g.sigla_unidade_responsavel_acompanhamento,
    g.unidade_responsavel_acompanhamento,
    g.tx_nome_institucional_programa as nome_institucional_programa,
    g.tx_objetivo_programa as objetivo_programa,
    g.in_autoriza_subdescentralizacao_outro = 'S' as autoriza_subdescentralizacao,
    g.in_autoriza_realizacao_despesas = 'S' as autoriza_realizacao_despesas,
    g.in_autoriza_execucao_creditos_descentralizada
    = 'S' as autoriza_execucao_creditos_descentralizada,

    -- Origem do recurso
    case
        when o.tem_emenda
        then 'Emenda'
        when o.id_plano_acao is not null
        then 'Recurso próprio'
        else 'Não identificada'
    end as origem_recurso,
    coalesce(o.tem_emenda and o.tem_proprio, false) as complemento_proprio
from planos as p
inner join {{ ref("ted_plano_instrumento") }} as i on i.id_plano_acao = p.id_plano_acao
left join programas as g on g.id_programa = p.id_programa
left join origem as o on o.id_plano_acao = p.id_plano_acao
