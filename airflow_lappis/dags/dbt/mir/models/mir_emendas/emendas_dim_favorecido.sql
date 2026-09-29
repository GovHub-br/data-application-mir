{{ config(alias="dim_favorecido") }}

-- Favorecidos das NEs de emenda, pelo CPF/CNPJ. CPF de pessoa fisica aparece
-- mascarado (***12345***, mesmo formato do SICONV); a chave usa o documento
-- completo. Nome da NE mais recente.
select
    {{ surrogate_key(["favorecido_documento"]) }} as sk_favorecido,
    case
        when length(favorecido_documento) = 11
        then '***' || substr(favorecido_documento, 4, 5) || '***'
        else favorecido_documento
    end as favorecido_documento,
    favorecido_nome,
    case
        length(favorecido_documento)
        when 14
        then 'PJ'
        when 11
        then 'PF'
        else 'Não identificado'
    end as favorecido_tipo
from
    (
        select distinct on (favorecido_documento) favorecido_documento, favorecido_nome
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null and favorecido_documento is not null
        order by favorecido_documento, data_emissao desc
    ) as f

union all

select -1::bigint, '-1', 'Não identificado', 'Não identificado'
