{{ config(materialized="table") }}

-- Cobertura do identificador do parceiro (UG/CNPJ) por tipo de instrumento.
-- Sem identificador o instrumento entra no Coleta MIR, mas nenhum gestor
-- consegue pedir acesso a ele.
select
    tp_instrumento,
    count(*)::integer as qt_total,
    count(*) filter (where co_identificador is null)::integer as qt_sem_identificador,
    round(
        100.0 * count(*) filter (where co_identificador is not null) / count(*), 2
    )::numeric(5, 2) as pc_cobertura
from {{ ref("coleta_instrumento") }}
group by tp_instrumento
