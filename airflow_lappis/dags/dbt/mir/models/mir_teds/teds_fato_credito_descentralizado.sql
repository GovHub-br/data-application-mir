{{ config(alias="fato_credito_descentralizado") }}

-- Credito descentralizado (NC) dos TEDs, um movimento por linha. NC sem plano no
-- TransfereGov fica com plano -1, mas mantem o num_transf. PTRES, natureza e
-- fonte ficam como colunas degeneradas.
select
    n.id_movimento,
    n.nc,
    {{ fk(["n.id_plano_acao"]) }} as sk_plano_acao,
    {{ sk_tempo("n.data_movimento") }} as sk_tempo,
    {{ fk(["n.ug_executora_codigo"]) }} as sk_unidade_executora,
    n.tipo,
    n.evento,
    n.num_transf,
    n.metodo_vinculo,
    n.data_estimada,
    n.ptres,
    n.natureza_despesa,
    n.fonte_recursos,
    n.valor
from {{ ref("ted_credito_nc") }} as n
