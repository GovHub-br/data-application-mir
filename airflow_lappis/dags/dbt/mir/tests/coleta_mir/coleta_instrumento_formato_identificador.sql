{{ config(severity="warn") }}

-- Formato do identificador do parceiro: UG com 6 digitos, CNPJ com 14, e
-- tp_identificador e co_identificador nulos juntos.
select chave, tp_identificador, co_identificador
from {{ ref("coleta_instrumento") }}
where
    (tp_identificador = 'ug' and co_identificador !~ '^\d{6}$')
    or (tp_identificador = 'cnpj' and co_identificador !~ '^\d{14}$')
    or ((tp_identificador is null) <> (co_identificador is null))
