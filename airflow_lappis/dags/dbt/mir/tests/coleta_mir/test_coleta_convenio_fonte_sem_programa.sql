{{ config(severity="warn") }}

{#
  Programa, ação e UO vêm do relatório de execução do PPA, pelo convênio, ano e PTRES do
  empenho. Para convênio assinado desde 2023 a linha sem programa quer dizer que o
  relatório não tem a NE (carga atrasada) ou que ela cita o convênio de outro jeito. Os
  anteriores a 2023 ficam de fora: o relatório não os cobre.
#}
select f.nr_convenio, f.aa_emissao, f.cd_ptres, f.vl_empenhado
from {{ ref("coleta_convenio_fonte") }} as f
inner join {{ ref("coleta_convenio") }} as c on c.nr_convenio = f.nr_convenio
where f.cd_programa is null and c.dt_assinatura >= '2023-01-01'
