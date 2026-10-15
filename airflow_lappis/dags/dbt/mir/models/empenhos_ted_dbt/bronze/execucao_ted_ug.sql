{{ config(materialized="table") }}

{#
  Relatório "Execução TED por UG" do Tesouro Gerencial
  (email_execucao_ted_ug_ingest_dag): a consulta oficial do MIR para o gasto com
  TEDs, no grão ano x UG executora x ação x PO x PTRES x grupo x fonte. Os valores
  são saldo acumulado do ano na data da extração; a DAG substitui os anos que
  cada anexo traz, então a tabela raw já tem uma linha por célula.
#}
select
    ano_lancamento::integer as ano_lancamento,
    orgao_uge_codigo,
    orgao_uge_nome,
    ug_executora_codigo,
    ug_executora_nome,
    acao_governo_codigo,
    acao_governo_nome,
    plano_orcamentario_codigo,
    plano_orcamentario_nome,
    ptres,
    grupo_despesa,
    fonte_recursos_detalhada,
    {{ parse_financial_value("destaque_recebido") }} as destaque_recebido,
    {{ parse_financial_value("credito_disponivel") }} as credito_disponivel,
    {{ parse_financial_value("despesas_empenhadas") }} as despesas_empenhadas,
    {{ parse_financial_value("despesas_liquidadas") }} as despesas_liquidadas,
    {{ parse_financial_value("despesas_pagas") }} as despesas_pagas,
    (dt_ingest || '-03:00')::timestamptz as dt_ingest
from {{ source("siafi", "execucao_ted_ug") }}
