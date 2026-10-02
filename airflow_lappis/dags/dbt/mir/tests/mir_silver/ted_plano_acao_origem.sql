-- Falha se a origem do recurso do plano contradisser as NEs do nucleo:
-- * Emenda exige alguma NE de emenda;
-- * Recurso proprio exige NE e nenhuma de emenda;
-- * Nao identificada exige ausencia de NE;
-- * complemento_proprio so em Emenda com NE de recurso proprio.
with
    nes as (
        select
            nr_instrumento::integer as id_plano_acao,
            bool_or(origem_recurso = 'Emenda') as tem_emenda,
            bool_or(origem_recurso = 'Recurso próprio') as tem_proprio
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'TED'
        group by nr_instrumento
    )

select p.id_plano_acao, p.origem_recurso, p.complemento_proprio
from {{ ref("ted_plano_acao") }} as p
left join nes as n on n.id_plano_acao = p.id_plano_acao
where
    (p.origem_recurso = 'Emenda' and not coalesce(n.tem_emenda, false))
    or (
        p.origem_recurso = 'Recurso próprio' and (n.id_plano_acao is null or n.tem_emenda)
    )
    or (p.origem_recurso = 'Não identificada' and n.id_plano_acao is not null)
    or (
        p.complemento_proprio
        <> (p.origem_recurso = 'Emenda' and coalesce(n.tem_proprio, false))
    )
