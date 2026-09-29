-- Falha se algum instrumento de NE de emenda (fora os nao identificados) faltar
-- em emenda_instrumento ou ficar sem tipo.
select distinct x.sistema_instrumento, x.nr_instrumento
from {{ ref("execucao_ne") }} as x
left join
    {{ ref("emenda_instrumento") }} as i
    on i.sistema_instrumento = x.sistema_instrumento
    and i.nr_instrumento = x.nr_instrumento
where
    x.codigo_emenda is not null
    and x.sistema_instrumento <> 'Não identificado'
    and i.tipo_instrumento is null
