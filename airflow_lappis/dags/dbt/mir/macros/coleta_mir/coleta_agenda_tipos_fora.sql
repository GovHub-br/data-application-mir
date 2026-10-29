{#
  Tipos do catálogo de agendas do PPA que não entram em coleta_lista_agenda, porque o
  formulário de TEDs só pergunta por agendas transversais e ODS: as agendas prioritárias
  (Combate à Fome, Novo PAC…), as agendas transversais territoriais (PRDA, PRDNE, PRDCO)
  e o PPA Participativo. Dois consumidores: coleta_lista_agenda (o que fica de fora) e
  test_coleta_lista_agenda_catalogo_completo (avisa quando um tipo novo do SIOP não
  vira linha).
#}
{% macro coleta_agenda_tipos_fora() -%}
    ('Prioridade', 'Agenda Transversal Territorial', 'PPA Participativo')
{%- endmacro %}
