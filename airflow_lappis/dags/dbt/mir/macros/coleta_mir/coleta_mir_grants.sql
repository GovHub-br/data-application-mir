{#
  Dá ao papel do Coleta MIR (var coleta_mir_leitor) leitura da tabela e uso do schema.
  É post-hook, e não a config grants, porque a config é renderizada antes de o dbt ler
  os vars do dbt_project.yml. Roda a cada build porque a tabela é recriada e perde os
  grants. Com a var vazia, não faz nada.
#}
{% macro coleta_mir_grants() -%}
    {%- set leitor = var("coleta_mir_leitor", "") -%}
    {%- if leitor -%}
        grant usage on schema {{ this.schema }} to {{ leitor }};
        grant select on {{ this }} to {{ leitor }}
    {%- endif -%}
{%- endmacro %}
