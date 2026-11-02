{{ config(severity="warn") }}

{#
  Todo TED da gold, sozinho ou dentro de instrumento mesclado, vira linha em
  coleta_ted_execucao. Um que não vira tem execução e não tem plano no portal TED, então o
  formulário não o mostra. 1ABDUQ e 698627 já são conhecidos e estão fora do escopo; ficam
  de fora para o aviso só aparecer em caso novo.
#}
with
    partes as (
        select g.ano, g.instrumento, g.empenhado, p.parte as nr_transferencia
        from {{ ref("ted_execucao_por_instrumento") }} as g
        cross join lateral unnest(string_to_array(g.instrumento, ' + ')) as p(parte)
        where g.tipo_instrumento = 'TED'
    )

select p.ano, p.instrumento, p.nr_transferencia, p.empenhado
from partes as p
left join {{ ref("coleta_ted") }} as c on c.nr_transferencia = p.nr_transferencia
left join {{ ref("coleta_ted_execucao") }} as e on e.id_plano_acao = c.id_plano_acao
where
    e.id_plano_acao is null
    and p.nr_transferencia not like 'tedinho%'
    and p.nr_transferencia not in ('1ABDUQ', '698627')
