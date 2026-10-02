{{ config(alias="fato_execucao_orcamentaria") }}

-- Execucao orcamentaria das emendas: todas as linhas do nucleo com codigo de
-- emenda, de qualquer instrumento (convenio do MIR, TED, convenio de outro
-- orgao ou execucao direta / nao identificado). A emenda, o parlamentar e o
-- localizador vem da NE.
select
    x.id_execucao_ne,
    x.ne_ccor,
    {{ fk(["x.codigo_emenda"]) }} as sk_emenda,
    {{ fk(["e.id_parlamentar", "e.cargo_parlamentar", "e.sigla_partido"]) }}
    as sk_parlamentar,
    {{ fk(["nullif(x.sistema_instrumento, 'Não identificado')", "x.nr_instrumento"]) }}
    as sk_instrumento_executor,
    {{ fk(["x.favorecido_documento"]) }} as sk_favorecido,
    {{ fk(["e.localizador_gasto"]) }} as sk_localidade,
    {{ sk_tempo("x.data_emissao") }} as sk_tempo,
    {{ fk(["x.ug_responsavel_codigo"]) }} as sk_unidade_gestora,
    {{ fk(["x.ptres"]) }} as sk_acao_orcamentaria,
    {{ fk(["x.natureza_despesa"]) }} as sk_natureza_despesa,
    {{ fk(["x.fonte_recursos_detalhada"]) }} as sk_fonte_recurso,
    x.metodo_vinculo,
    x.inscricao_rap,
    x.reinscricao_rap,
    x.despesas_empenhadas,
    x.despesas_liquidadas,
    x.despesas_pagas,
    x.restos_a_pagar_inscritos,
    -- RAP inscrito sem as reinscricoes (saldo nao pago do mesmo dinheiro): e a
    -- medida que pode ser somada entre exercicios
    case
        when x.reinscricao_rap then 0 else x.restos_a_pagar_inscritos
    end as restos_a_pagar_inscritos_acumulavel,
    x.restos_a_pagar_pagos
from {{ ref("execucao_ne") }} as x
left join {{ ref("emenda_ne") }} as e on e.ne_ccor = x.ne_ccor
where x.codigo_emenda is not null
