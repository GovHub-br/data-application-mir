-- Convenente (proponente) dos convenios do MIR, pelo CNPJ. Quando o mesmo CNPJ
-- aparece com nomes diferentes, fica o do convenio assinado mais recentemente.
select {{ surrogate_key(["convenente_documento"]) }} as sk_convenente, c.*
from
    (
        select distinct
            on (convenente_documento)
            convenente_documento,
            convenente_nome,
            convenente_natureza_juridica
        from {{ ref("convenio_mir") }}
        where convenente_documento is not null
        order by convenente_documento, data_assinatura desc nulls last
    ) as c

union all

select -1::bigint, '-1', 'Não identificado', 'Não identificado'
