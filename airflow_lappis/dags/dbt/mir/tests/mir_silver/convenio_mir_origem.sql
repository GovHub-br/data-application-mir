-- Falha se a origem do recurso do convenio contradisser as NEs do nucleo:
-- * Emenda exige alguma NE de emenda;
-- * Recurso proprio exige NE e nenhuma de emenda;
-- * Nao identificada exige ausencia de NE;
-- * complemento_proprio so em Emenda com NE de recurso proprio.
with
    nes as (
        select
            nr_instrumento as nr_convenio,
            bool_or(origem_recurso = 'Emenda') as tem_emenda,
            bool_or(origem_recurso = 'Recurso próprio') as tem_proprio
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'SICONV'
        group by nr_instrumento
    )

select c.nr_convenio, c.origem_recurso, c.complemento_proprio
from {{ ref("convenio_mir") }} as c
left join nes as n on n.nr_convenio = c.nr_convenio
where
    (c.origem_recurso = 'Emenda' and not coalesce(n.tem_emenda, false))
    or (c.origem_recurso = 'Recurso próprio' and (n.nr_convenio is null or n.tem_emenda))
    or (c.origem_recurso = 'Não identificada' and n.nr_convenio is not null)
    or (
        c.complemento_proprio
        <> (c.origem_recurso = 'Emenda' and coalesce(n.tem_proprio, false))
    )
