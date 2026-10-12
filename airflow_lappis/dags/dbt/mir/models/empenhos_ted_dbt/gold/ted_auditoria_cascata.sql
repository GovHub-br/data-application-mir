{{ config(materialized="table") }}

{#
  Auditoria da cascata de extração de num_transf: para onde vai cada real de
  empenho que passa pela cascata, e por qual motivo.

  Issue #508, critério de aceite: existir um número fechado explicando a
  diferença de empenhado/liquidado entre o painel e o levantamento da CGPO,
  decomposto por motivo. Este modelo é esse número. Toda NE de ppa_tesouro
  (exceto as linhas de dotação, ne_ccor = '-9', que não são NE) cai em
  exatamente uma linha de agregação, então as somas fecham com o total da
  cascata e nenhum valor fica fora do relatório — garantido por
  test_ted_auditoria_cascata_fecha.

  Os dois blocos são disjuntos e cobrem a cascata inteira: empenhos_ted_residuo
  é, por definição, a cascata com num_transf nulo. Por isso o relatório os
  agrega separado e une, em vez de juntar o resíduo de volta na cascata por
  ne_ccor — esse join seria de milhão por milhão sem necessidade, e ne_ccor não
  serve como chave de linha (há NE com linhas vinculadas e não vinculadas na
  mesma chave).

  Eixos:
    destino            -- 'painel' se a NE entra no empenhado da gold
                          (num_transf preenchido); 'residuo' caso contrário.
    categoria_residuo  -- para o resíduo, o motivo (a/b/c/d da issue #508 e 'e',
                          a exclusão de Convênio/Termo de Fomento da #510).
    descartado_em      -- em qual filtro a linha morreu: 'silver' ou 'gold'.
    metodo             -- o método da cascata que resolveu (ou não) a NE.

  Não há eixo de tipo de instrumento: desde a issue #510 (PR #79) a cascata já
  descarta na origem qualquer número que exista no cadastro do SICONV, então o
  que chega ao painel não é mais contaminado por Convênio/Termo de Fomento. O
  volume dessa exclusão fica visível na categoria 'e_excluido_siconv'.

  Convenção de valor idêntica à de valores_empenhados_tb em
  ted_resumo_orcamentario: empenhado conta só despesas_empenhadas positivas e a
  anulação vai para empenho_anulado, para que os números deste relatório sejam
  comparáveis com os do painel sem ajuste.
#}

with
    painel as (
        select
            'painel' as destino,
            cast(null as text) as categoria_residuo,
            cast(null as text) as descartado_em,
            metodo,
            num_transf,
            despesas_empenhadas,
            despesas_liquidadas,
            despesas_pagas,
            restos_a_pagar_inscritos,
            restos_a_pagar_pagos,
            dt_ingest
        from {{ ref("empenhos_ted_cascata") }}
        where num_transf is not null
    ),

    residuo as (
        select
            'residuo' as destino,
            categoria_residuo,
            descartado_em,
            metodo,
            num_transf,
            despesas_empenhadas,
            despesas_liquidadas,
            despesas_pagas,
            restos_a_pagar_inscritos,
            restos_a_pagar_pagos,
            dt_ingest
        from {{ ref("empenhos_ted_residuo") }}
    ),

    unificado as (
        select * from painel
        union all
        select * from residuo
    )

select
    destino,
    categoria_residuo,
    descartado_em,
    metodo,
    count(*) as qtd_nes,
    count(distinct num_transf) as qtd_instrumentos,
    sum(
        case when despesas_empenhadas > 0 then despesas_empenhadas else 0 end
    ) as empenhado,
    sum(
        case when despesas_empenhadas < 0 then -despesas_empenhadas else 0 end
    ) as empenho_anulado,
    sum(despesas_liquidadas) as liquidado,
    sum(despesas_pagas) as pago,
    sum(restos_a_pagar_inscritos) as restos_a_pagar,
    sum(restos_a_pagar_pagos) as restos_a_pagar_pagos,
    max(dt_ingest) as dt_ingest
from unificado
group by destino, categoria_residuo, descartado_em, metodo
