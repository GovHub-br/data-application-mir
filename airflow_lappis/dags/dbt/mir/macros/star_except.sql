{#
  Gera uma lista de colunas separadas por vírgula a partir de uma lista Jinja de nomes
  (não introspecta o banco — `adapter.get_columns_in_relation` não funciona aqui porque
  as CTEs da cascata de métodos são efêmeras, não relações materializadas). Usado para
  evitar repetir manualmente a lista de colunas em cada CTE da cascata de extração de
  identificadores em empenhos_por_plano_acao.sql.
#}
{% macro star_except(columns, except_columns=[], prefix='') %}
{%- set filtered = [] -%}
{%- for col in columns -%}
    {%- if col not in except_columns -%}
        {%- do filtered.append(prefix ~ col) -%}
    {%- endif -%}
{%- endfor -%}
{{- filtered | join(', ') -}}
{% endmacro %}
