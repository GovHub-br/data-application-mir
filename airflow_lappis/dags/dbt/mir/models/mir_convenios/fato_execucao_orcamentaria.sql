-- Execucao orcamentaria dos convenios do MIR: linhas do nucleo execucao_ne
-- vinculadas a um convenio do universo convenio_mir, no mesmo grao (linha do
-- relatorio do Tesouro). Convenios de outros orgaos com NE no relatorio do MIR
-- ficam fora (entram so no mart de Emendas). A emenda e o parlamentar vem da
-- NE; linha de recurso proprio fica com emenda e parlamentar -1, e NE de
-- emenda cujo autor nao foi encontrado fica so com parlamentar -1.
select
    x.id_execucao_ne,
    x.ne_ccor,
    {{ fk(["x.nr_instrumento"]) }} as sk_convenio,
    {{ sk_tempo("x.data_emissao") }} as sk_tempo,
    {{ fk(["x.ug_responsavel_codigo"]) }} as sk_unidade_gestora,
    {{ fk(["x.ptres"]) }} as sk_acao_orcamentaria,
    {{ fk(["x.natureza_despesa"]) }} as sk_natureza_despesa,
    {{ fk(["x.fonte_recursos_detalhada"]) }} as sk_fonte_recurso,
    {{ fk(["x.codigo_emenda"]) }} as sk_emenda,
    {{ fk(["e.id_parlamentar", "e.cargo_parlamentar", "e.sigla_partido"]) }}
    as sk_parlamentar,
    x.origem_recurso,
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
inner join {{ ref("convenio_mir") }} as c on c.nr_convenio = x.nr_instrumento
left join {{ ref("emenda_ne") }} as e on e.ne_ccor = x.ne_ccor
where x.sistema_instrumento = 'SICONV'
