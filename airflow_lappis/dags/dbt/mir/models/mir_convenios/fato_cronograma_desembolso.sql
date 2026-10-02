-- Parcelas previstas no cronograma de desembolso, ligadas ao mes previsto
-- (primeiro dia do mes).
select
    c.id_parcela,
    {{ fk(["c.nr_convenio"]) }} as sk_convenio,
    {{ sk_tempo("c.data_prevista") }} as sk_tempo,
    c.nr_parcela,
    c.responsavel,
    c.valor_previsto
from {{ ref("convenio_cronograma") }} as c
