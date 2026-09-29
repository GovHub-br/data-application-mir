{{ config(alias="fato_programacao_financeira") }}

-- Programacao financeira (PF) dos TEDs, um movimento por linha. PF sem plano no
-- TransfereGov fica com plano -1, mas mantem o num_transf.
select
    f.id_movimento,
    f.pf,
    {{ fk(["f.id_plano_acao"]) }} as sk_plano_acao,
    {{ sk_tempo("f.data_movimento") }} as sk_tempo,
    {{ fk(["f.ug_executora_codigo"]) }} as sk_unidade_executora,
    f.tipo,
    f.evento,
    f.num_transf,
    f.fonte_recursos,
    f.valor
from {{ ref("ted_programacao_pf") }} as f
