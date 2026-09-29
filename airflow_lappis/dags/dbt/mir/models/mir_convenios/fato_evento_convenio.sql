-- Eventos administrativos dos convenios (mudanca de situacao, aditivo,
-- prorrogacao, solicitacoes), um por linha. quantidade = 1 permite contar
-- eventos com soma no Power BI.
select
    e.id_evento,
    {{ fk(["e.nr_convenio"]) }} as sk_convenio,
    {{ sk_tempo("e.data_evento") }} as sk_tempo,
    e.tipo_evento,
    e.situacao,
    e.descricao,
    1 as quantidade,
    e.valor,
    e.valor_aprovado,
    e.dias,
    e.data_fim_nova
from {{ ref("convenio_evento") }} as e
