{{ config(materialized="table") }}

{#
  Resíduo da cascata de extração de num_transf: as NEs que NÃO contribuem com
  empenhado para o painel de TED, cada uma com o motivo.

  Issue #508. O critério é num_transf nulo, porque é num_transf que decide se a
  NE vira empenhado na gold (valores_empenhados_tb agrega
  `where num_transf is not null`). NE com num_transf preenchido fica fora daqui.

  Os dois filtros que eliminam linha, agora explícitos na coluna descartado_em:

    'silver' -- empenhos_por_plano_acao filtra
              `(nc != '') or (num_transf is not null) or metodo = 'excluido: ...'`.
              Quem chega sem nc, sem num_transf e sem o rótulo de exclusão não
              entra no modelo e, portanto, em nada a jusante.
    'gold'   -- a NE sobrevive à silver (tem NC, ou é exclusão SICONV rotulada)
              mas o `where num_transf is not null` de valores_empenhados_tb a
              deixa fora do somatório de empenhado.

  categoria_residuo segue a decomposição pedida na issue, mais a categoria 'e',
  criada pela issue #510 (PR #79), com precedência e > d > c > b > a:

    'e_excluido_siconv'          -- o número extraído existe no cadastro do
                                    SICONV, então não é TED: Convênio/Termo de
                                    Fomento descartado de propósito pela rede de
                                    segurança da cascata. NÃO é perda — é o
                                    conserto do bucket "Em Branco" funcionando.
                                    Precede as demais porque uma dessas NEs pode
                                    também ter NC e seria rotulada como 'c'.
    'd_ted_sem_vinculo'          -- a NE declara "TED S/V"/"sem vínculo". Não
                                    deveria entrar mesmo; é resíduo legítimo.
    'c_nc_sem_transferencia'     -- tem NC, mas a NC não resolve transferência.
    'b_menciona_ted_sem_captura' -- o texto menciona TED/transferência num
                                    formato que nenhum regex capturou. É desta
                                    categoria que sairiam novos métodos.
    'a_sem_mencao_ted'           -- nenhuma menção a TED em nenhum dos campos de
                                    texto lidos pela cascata. Orçamento próprio
                                    da UG, não TED.

  Mesmo escopo de governo inteiro da cascata: a categoria 'a' domina em volume e
  é esperada — é o orçamento das outras UGs, não perda do MIR. O que interessa
  para a reconciliação com a CGPO são as categorias 'b' e 'c'.
#}

with
    residuo as (
        select *
        from {{ ref("empenhos_ted_cascata") }}
        where num_transf is null
    ),

    -- Mesmos campos de texto que a cascata inspeciona, concatenados para a
    -- checagem de menção. Deliberadamente mais larga que os regex de captura:
    -- aqui o objetivo é achar NE em que um humano reconheceria uma referência a
    -- TED que os regex deixaram passar, e não extrair o número.
    com_texto as (
        select
            *,
            concat_ws(
                ' | ',
                ne_ccor_descricao,
                doc_observacao,
                ne_info_complementar,
                fonte_recursos_detalhada_descricao
            ) as texto_busca
        from residuo
    ),

    classificado as (
        select
            *,
            (
                texto_busca ~* '\mTED\M'
                or texto_busca ~* 'TRANSFEREGOV'
                or texto_busca ~* 'DESCENTRALIZA'
                or texto_busca ~* 'TERMO\s+DE\s+EXECUCAO'
                or texto_busca ~* 'NOTA\s+DE\s+(TRANS|TRANF)FERENCIA'
                or texto_busca ~* '\mNT\M'
            ) as menciona_ted,
            (metodo = 'excluido: numero e de convenio/termo de fomento (SICONV)')
                as excluido_siconv,
            (nc is not null and nc <> '') as tem_nc
        from com_texto
    )

select
    ne_ccor,
    ne,
    orgao_id,
    ug_responsavel_codigo,
    ug_responsavel_nome,
    emissao_dia,
    nc,
    num_transf,
    metodo,
    case
        when excluido_siconv then 'e_excluido_siconv'
        when metodo = 'sem vinculo' then 'd_ted_sem_vinculo'
        when tem_nc then 'c_nc_sem_transferencia'
        when menciona_ted then 'b_menciona_ted_sem_captura'
        else 'a_sem_mencao_ted'
    end as categoria_residuo,
    case when tem_nc or excluido_siconv then 'gold' else 'silver' end
        as descartado_em,
    menciona_ted,
    despesas_empenhadas,
    despesas_liquidadas,
    despesas_pagas,
    restos_a_pagar_inscritos,
    restos_a_pagar_pagos,
    ne_ccor_descricao,
    doc_observacao,
    ne_info_complementar,
    dt_ingest
from classificado
