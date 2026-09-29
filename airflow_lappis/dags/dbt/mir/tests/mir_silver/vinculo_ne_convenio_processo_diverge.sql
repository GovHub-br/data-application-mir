{{ config(severity="warn") }}

-- Aviso (nao bloqueia a DAG): NE vinculada a um convenio cujo nr_processo nao
-- aparece em nenhuma linha da NE. O vinculo e mantido; o aviso sinaliza
-- possivel erro de digitacao no numero do instrumento ou um caso novo (ex.:
-- empenho em nome de fundo ou mandataria). Linha de base em 2026-09-29: 0.
with
    processos_ne as (
        select distinct ne_ccor, ne_num_processo
        from {{ ref("ppa_tesouro") }}
        where ne_ccor <> '-9'
    )

select v.ne_ccor, v.nr_convenio, c.nr_processo
from {{ ref("vinculo_ne_convenio") }} as v
inner join {{ ref("convenio") }} as c on c.nr_convenio = v.nr_convenio
where
    not exists (
        select 1
        from processos_ne as p
        where p.ne_ccor = v.ne_ccor and p.ne_num_processo = c.nr_processo
    )
