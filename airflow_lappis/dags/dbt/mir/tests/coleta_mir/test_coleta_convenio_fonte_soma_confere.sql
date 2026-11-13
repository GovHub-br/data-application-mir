{#
  A soma de vl_empenhado de cada convênio tem de ser o empenho dele no siconv. Uma
  junção que duplique linhas (duas emendas para a mesma NE, um PTRES com dois programas)
  ou que perca NE muda a soma.
#}
with
    siconv as (
        select e.nr_convenio, sum(e.valor_empenho) as vl_empenhado
        from {{ ref("empenho") }} as e
        inner join {{ ref("coleta_convenio") }} as c on c.nr_convenio = e.nr_convenio
        group by e.nr_convenio
    ),

    fonte as (
        select nr_convenio, sum(vl_empenhado) as vl_empenhado
        from {{ ref("coleta_convenio_fonte") }}
        group by nr_convenio
    )

select s.nr_convenio, s.vl_empenhado as siconv, f.vl_empenhado as fonte
from siconv as s
full join fonte as f on f.nr_convenio = s.nr_convenio
where s.vl_empenhado is distinct from f.vl_empenhado
