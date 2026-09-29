{#
    Falha se a dimensao nao tem o membro -1 (Nao identificado), para onde vao
    as FKs nulas das fatos.
#}
{% test membro_nao_identificado(model, column_name) %}
    select 1 as membro_ausente
    where not exists (select 1 from {{ model }} where {{ column_name }} = -1)
{% endtest %}
