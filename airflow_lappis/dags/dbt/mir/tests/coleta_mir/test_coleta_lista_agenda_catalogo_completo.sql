{{ config(severity="warn") }}

{#
  Todo item do catálogo de agendas (revisões a partir de 2025) vira linha em
  coleta_lista_agenda, salvo os tipos de coleta_agenda_tipos_fora(). Uma subagenda só
  entra se o tipo dela casar com o nome de uma agenda transversal; se o SIOP criar um
  tipo novo ou renomear uma agenda, o item some da lista sem erro, e este teste avisa.
#}
select a.ano_ppa, a.tipo, a.codigo, a.nome
from {{ ref("agenda") }} as a
left join {{ ref("coleta_lista_agenda") }} as c on c.chave = 'agenda:' || a.codigo
where
    a.ano_ppa >= 2025
    and a.tipo not in {{ coleta_agenda_tipos_fora() }}
    and c.chave is null
