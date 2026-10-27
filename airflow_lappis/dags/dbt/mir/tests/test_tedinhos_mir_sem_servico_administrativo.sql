-- Falha se uma NC de tedinho tiver alguma celula para UG de servico compartilhado
-- (CSC/MGI, Diarias e Passagens, Central de Compras, logistica do MDHC) ou em acao
-- administrativa. Essas NCs pagam a operacao do proprio MIR, nao um parceiro, e
-- eram ~95% do credito de tedinho antes de servico_administrativo. As celulas vem
-- da fonte (nc_tesouro_mir, no mesmo escopo de tedinhos_mir), nao das colunas do
-- modelo, para o teste nao depender da expressao que ele verifica. Como a regra e
-- do instrumento, qualquer celula administrativa ja reprova a NC.
select distinct
    t.instrumento_key,
    t.nc,
    n.favorecido_doc,
    n.favorecido_doc_descricao,
    n.acao_governo
from {{ ref("tedinhos_mir") }} as t
join {{ ref("nc_tesouro_mir") }} as n on n.nc = t.nc
where
    t.tedinho_provavel
    and n.relatorio = 'enviadas'
    and n.nc_evento_descricao ilike '%DESCENTRALIZACAO DE CREDITO%'
    and (
        n.favorecido_doc in {{ ted_execucao_ugs_excluidas() }}
        or upper(n.acao_governo) in {{ ted_execucao_acoes_excluidas() }}
    )
