-- Falha se alguma NC classificada como tedinho for para uma UG de servico
-- compartilhado (CSC/MGI, Diarias e Passagens, Central de Compras, logistica do
-- MDHC). Essas NCs pagam a operacao do proprio MIR, nao um parceiro, e eram ~95%
-- do credito de tedinho antes da regra de servico_administrativo. O favorecido
-- vem da fonte (nc_tesouro_mir), nao da coluna do modelo, para o teste nao
-- depender da mesma expressao que ele verifica.
select
    t.instrumento_key,
    t.nc,
    n.favorecido_doc,
    n.favorecido_doc_descricao
from {{ ref("tedinhos_mir") }} as t
join
    (
        select distinct nc, favorecido_doc, favorecido_doc_descricao
        from {{ ref("nc_tesouro_mir") }}
    ) as n
    on n.nc = t.nc
where t.tedinho_provavel and n.favorecido_doc in {{ ted_execucao_ugs_excluidas() }}
