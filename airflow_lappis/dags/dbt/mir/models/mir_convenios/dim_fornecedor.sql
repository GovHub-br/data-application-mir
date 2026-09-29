-- Fornecedores pagos com recurso dos convenios do MIR. O SICONV ja publica o
-- CPF mascarado; a chave de pessoa fisica e documento mascarado + nome (regra
-- em convenio_movimento_financeiro). Para PJ com nomes diferentes no mesmo
-- CNPJ, fica o nome do pagamento mais recente.
select {{ surrogate_key(["fornecedor_chave"]) }} as sk_fornecedor, f.*
from
    (
        select distinct
            on (fornecedor_chave)
            fornecedor_chave,
            fornecedor_documento,
            fornecedor_nome,
            fornecedor_tipo
        from {{ ref("convenio_movimento_financeiro") }}
        where fornecedor_chave is not null
        order by fornecedor_chave, data_movimento desc nulls last, id_movimento
    ) as f

union all

select -1::bigint, '-1', null, 'Não identificado', 'Não identificado'
