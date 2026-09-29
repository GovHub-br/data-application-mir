{{ config(materialized="table") }}

-- Cronograma de desembolso previsto dos convenios do MIR, uma linha por
-- convenio x parcela x responsavel. A data prevista e o primeiro dia do mes.
select
    md5(
        concat_ws(
            '|',
            c.nr_convenio,
            c.nr_parcela_crono_desembolso,
            c.tipo_resp_crono_desembolso
        )
    ) as id_parcela,
    c.nr_convenio,
    c.nr_parcela_crono_desembolso as nr_parcela,
    c.tipo_resp_crono_desembolso as responsavel,
    make_date(c.ano_crono_desembolso, c.mes_crono_desembolso, 1) as data_prevista,
    c.valor_parcela_crono_desembolso as valor_previsto
from {{ ref("cronograma_desembolso") }} as c
inner join {{ ref("convenio_mir") }} as mir on mir.nr_convenio = c.nr_convenio
