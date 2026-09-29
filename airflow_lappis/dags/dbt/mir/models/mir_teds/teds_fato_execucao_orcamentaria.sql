{{ config(alias="fato_execucao_orcamentaria") }}

-- Execucao orcamentaria dos TEDs: linhas do nucleo execucao_ne ligadas a um
-- plano de acao, no mesmo grao (linha do relatorio do Tesouro). empenhado_bruto
-- e empenho_anulado separam os valores positivos e negativos do empenhado
-- (mesma medida do gold antigo); despesas_empenhadas e o liquido. Linha de
-- recurso proprio fica com emenda e parlamentar -1, e NE de emenda cujo autor
-- nao foi encontrado fica so com parlamentar -1.
select
    x.id_execucao_ne,
    x.ne_ccor,
    {{ fk(["x.nr_instrumento"]) }} as sk_plano_acao,
    {{ sk_tempo("x.data_emissao") }} as sk_tempo,
    {{ fk(["x.ug_responsavel_codigo"]) }} as sk_unidade_gestora,
    {{ fk(["x.ptres"]) }} as sk_acao_orcamentaria,
    {{ fk(["x.natureza_despesa"]) }} as sk_natureza_despesa,
    {{ fk(["x.fonte_recursos_detalhada"]) }} as sk_fonte_recurso,
    {{ fk(["x.codigo_emenda"]) }} as sk_emenda,
    {{ fk(["e.id_parlamentar", "e.cargo_parlamentar", "e.sigla_partido"]) }}
    as sk_parlamentar,
    x.num_transf,
    x.origem_recurso,
    x.metodo_vinculo,
    x.inscricao_rap,
    x.reinscricao_rap,
    x.despesas_empenhadas,
    greatest(x.despesas_empenhadas, 0) as empenhado_bruto,
    greatest(- x.despesas_empenhadas, 0) as empenho_anulado,
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
where x.sistema_instrumento = 'TED'
