-- Falha se alguma NE de emenda do nucleo faltar em emenda_ne ou vier com outra
-- emenda.
with
    nucleo as (
        select distinct ne_ccor, codigo_emenda
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null
    )

select n.ne_ccor, n.codigo_emenda, e.codigo_emenda as codigo_emenda_ne
from nucleo as n
left join {{ ref("emenda_ne") }} as e on e.ne_ccor = n.ne_ccor
where e.codigo_emenda is distinct from n.codigo_emenda
