{{ config(materialized="table") }}

-- Planos de acao de TED do MIR, um por plano, juntando a API de dados abertos
-- (planos_acao_ted) e o portal do sistema TED (planos_acao_portal_ted). O portal
-- tem preferencia: ele mostra antes a situacao e o numero do instrumento (ex.:
-- TEDs de 2026 ja aprovados que nos dados abertos ainda aparecem em analise e sem
-- numero) e inclui planos que os dados abertos ainda nao publicaram. A API so
-- preenche o que o portal trouxer nulo. Mesmas colunas de planos_acao_ted, mais a
-- UG das unidades (so o portal tem) e a fonte de cada plano.
{% set colunas = [
    "id_programa",
    "sigla_unidade_descentralizada",
    "unidade_descentralizada",
    "sigla_unidade_responsavel_execucao",
    "unidade_responsavel_execucao",
    "vl_total_plano_acao",
    "dt_inicio_vigencia",
    "dt_fim_vigencia",
    "tx_objeto_plano_acao",
    "tx_justificativa_plano_acao",
    "in_forma_execucao_direta",
    "in_forma_execucao_particulares",
    "in_forma_execucao_descentralizada",
    "tx_situacao_plano_acao",
    "aa_ano_plano_acao",
    "vl_beneficiario_especifico",
    "vl_chamamento_publico",
    "sq_instrumento",
    "aa_instrumento",
] %}
with
    api as (
        select distinct on (id_plano_acao) *
        from {{ ref("planos_acao_ted") }}
        order by id_plano_acao, dt_ingest desc
    ),

    portal as (
        select distinct on (id_plano_acao) *
        from {{ ref("planos_acao_portal_ted") }}
        order by id_plano_acao, dt_ingest desc
    )

select
    coalesce(p.id_plano_acao, a.id_plano_acao) as id_plano_acao,
    {% for c in colunas %} coalesce(p.{{ c }}, a.{{ c }}) as {{ c }}, {% endfor %}
    p.cd_ug_unidade_descentralizada,
    p.cd_ug_unidade_responsavel_execucao,
    p.codigo_plano_acao,
    p.in_termo_execucao_assinado,
    case
        when p.id_plano_acao is not null and a.id_plano_acao is not null
        then 'portal e dados abertos'
        when p.id_plano_acao is not null
        then 'só portal'
        else 'só dados abertos'
    end as fonte,
    greatest(p.dt_ingest, a.dt_ingest) as dt_ingest
from portal as p
full join api as a on a.id_plano_acao = p.id_plano_acao
