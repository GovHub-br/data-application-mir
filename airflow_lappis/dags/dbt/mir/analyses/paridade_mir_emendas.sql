-- Paridade temporaria (spec §11): mart de Emendas x gold antigo. Apagar na
-- etapa 5, junto com o gold antigo. Dois blocos:
-- * por autor, contra resumo_emendas_orcamento_execucao (dotacao e execucao);
-- * por NE, o tipo do instrumento, contra emendas_instrumentos_execucao.
with
    antigo_autor as (
        select
            autor_emendas_orcamento_nome as autor,
            dotacao_inicial,
            dotacao_atualizada,
            despesas_empenhadas,
            despesas_liquidadas,
            despesas_pagas,
            restos_a_pagar_inscritos,
            restos_a_pagar_pagos
        from {{ ref("resumo_emendas_orcamento_execucao") }}
    ),

    novo_autor as (
        select
            e.autor_nome as autor,
            sum(p.dotacao_inicial) as dotacao_inicial,
            sum(p.dotacao_atualizada) as dotacao_atualizada,
            sum(p.despesas_empenhadas) as despesas_empenhadas,
            sum(p.despesas_liquidadas) as despesas_liquidadas,
            sum(p.despesas_pagas) as despesas_pagas,
            sum(p.restos_a_pagar_inscritos_acumulavel) as restos_a_pagar_inscritos,
            sum(p.restos_a_pagar_pagos) as restos_a_pagar_pagos
        from {{ ref("emendas_fato_emenda_posicao") }} as p
        inner join {{ ref("emendas_dim_emenda") }} as e on e.sk_emenda = p.sk_emenda
        group by e.autor_nome
    ),

    por_autor as (
        select coalesce(a.autor, n.autor) as chave, c.medida, c.valor_antigo, c.valor_novo
        from antigo_autor as a
        full join novo_autor as n on n.autor = a.autor
        cross join
            lateral(
                values
                    (
                        'presenca',
                        (a.autor is not null)::text,
                        (n.autor is not null)::text,
                        a.autor is null or n.autor is null
                    ),
                    (
                        'dotacao_inicial',
                        a.dotacao_inicial::text,
                        n.dotacao_inicial::text,
                        coalesce(a.dotacao_inicial, 0) <> coalesce(n.dotacao_inicial, 0)
                    ),
                    (
                        'dotacao_atualizada',
                        a.dotacao_atualizada::text,
                        n.dotacao_atualizada::text,
                        coalesce(a.dotacao_atualizada, 0)
                        <> coalesce(n.dotacao_atualizada, 0)
                    ),
                    (
                        'empenhado',
                        a.despesas_empenhadas::text,
                        n.despesas_empenhadas::text,
                        coalesce(a.despesas_empenhadas, 0)
                        <> coalesce(n.despesas_empenhadas, 0)
                    ),
                    (
                        'liquidado',
                        a.despesas_liquidadas::text,
                        n.despesas_liquidadas::text,
                        coalesce(a.despesas_liquidadas, 0)
                        <> coalesce(n.despesas_liquidadas, 0)
                    ),
                    (
                        'pago',
                        a.despesas_pagas::text,
                        n.despesas_pagas::text,
                        coalesce(a.despesas_pagas, 0) <> coalesce(n.despesas_pagas, 0)
                    ),
                    (
                        'rap_inscrito',
                        a.restos_a_pagar_inscritos::text,
                        n.restos_a_pagar_inscritos::text,
                        coalesce(a.restos_a_pagar_inscritos, 0)
                        <> coalesce(n.restos_a_pagar_inscritos, 0)
                    ),
                    (
                        'rap_pago',
                        a.restos_a_pagar_pagos::text,
                        n.restos_a_pagar_pagos::text,
                        coalesce(a.restos_a_pagar_pagos, 0)
                        <> coalesce(n.restos_a_pagar_pagos, 0)
                    )
            ) as c(medida, valor_antigo, valor_novo, difere)
        -- As medidas so sao comparadas nos autores presentes nos dois lados
        where
            c.difere
            and (c.medida = 'presenca' or (a.autor is not null and n.autor is not null))
    ),

    antigo_ne as (
        select ne_ccor, max(tipo_instrumento) as tipo
        from {{ ref("emendas_instrumentos_execucao") }}
        group by ne_ccor
    ),

    novo_ne as (
        select f.ne_ccor, max(i.tipo_instrumento) as tipo
        from {{ ref("emendas_fato_execucao_orcamentaria") }} as f
        inner join
            {{ ref("emendas_dim_instrumento_executor") }} as i
            on i.sk_instrumento_executor = f.sk_instrumento_executor
        group by f.ne_ccor
    ),

    por_ne as (
        select n.ne_ccor as chave, 'tipo_instrumento' as medida, a.tipo, n.tipo
        from novo_ne as n
        left join antigo_ne as a on a.ne_ccor = n.ne_ccor
        where
            case
                a.tipo
                when 'TERMO DE FOMENTO'
                then 'Fomento'
                when 'CONVENIO'
                then 'Convênio'
                when 'TED'
                then 'TED'
                else 'Execução direta / não identificado'
            end
            is distinct from n.tipo
    )

select 'autor' as bloco, chave, medida, valor_antigo, valor_novo
from por_autor

union all

select 'ne' as bloco, *
from por_ne
