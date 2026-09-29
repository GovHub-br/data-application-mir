{{ config(materialized="table") }}

-- Contagens de metas fisicas e licitacoes por convenio do MIR. O gold atual so
-- usa esses dados como contagens; o detalhe por meta ou licitacao vira fato
-- propria quando algum painel precisar.
with
    metas as (
        select
            nr_convenio,
            count(*) as qtd_metas,
            sum(vl_meta) as valor_metas,
            bool_or(data_fim_meta < current_date) as meta_expirada
        from {{ ref("meta_crono_fisico") }}
        group by nr_convenio
    ),

    licitacoes as (
        select
            nr_convenio,
            count(*) as qtd_licitacoes,
            sum(valor_licitacao) as valor_licitado
        from {{ ref("licitacao") }}
        group by nr_convenio
    )

select
    c.nr_convenio,
    coalesce(m.qtd_metas, 0) as qtd_metas,
    coalesce(m.valor_metas, 0) as valor_metas,
    coalesce(m.meta_expirada, false) as meta_expirada,
    coalesce(l.qtd_licitacoes, 0) as qtd_licitacoes,
    coalesce(l.valor_licitado, 0) as valor_licitado
from {{ ref("convenio_mir") }} as c
left join metas as m on m.nr_convenio = c.nr_convenio
left join licitacoes as l on l.nr_convenio = c.nr_convenio
