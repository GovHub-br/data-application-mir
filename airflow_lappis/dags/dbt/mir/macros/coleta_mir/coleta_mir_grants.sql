{#
  Dá ao papel do Coleta MIR (var coleta_mir_leitor) leitura da tabela e uso do schema.
  É post-hook, e não a config grants, porque a config é renderizada antes de o dbt ler
  os vars do dbt_project.yml. Roda a cada build porque a tabela é recriada e perde os
  grants. Com a var vazia, não faz nada. O papel vai entre aspas, então a var precisa
  ter o nome exato dele (minúsculo, se foi criado sem aspas).
#}
{% macro coleta_mir_grants() -%}
    {%- set leitor = var("coleta_mir_leitor", "") -%}
    {%- if leitor -%}
        grant usage on schema {{ this.schema }} to {{ adapter.quote(leitor) }};
        grant select on {{ this }} to {{ adapter.quote(leitor) }}
    {%- endif -%}
{%- endmacro %}
