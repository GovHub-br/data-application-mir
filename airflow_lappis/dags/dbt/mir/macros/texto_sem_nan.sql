{#
  Texto vindo de uma API sem os valores vazios: '' e o 'NaN' que a ingestão
  grava quando a API manda nulo (pandas) viram nulo, para os casts não quebrarem.
#}
{% macro texto_sem_nan(coluna) -%}
    nullif(nullif(trim({{ coluna }}::text), ''), 'NaN')
{%- endmacro %}
