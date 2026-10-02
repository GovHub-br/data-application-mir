-- Falha se a lista de codigos e a de nomes das UGs responsaveis nao estiverem
-- alinhadas: cada posicao i precisa formar um par (codigo, nome) que existe
-- nas NEs do convenio, e as duas listas precisam ter o mesmo tamanho.
with
    listas as (
        select
            nr_convenio,
            string_to_array(ug_responsavel_codigo, ', ') as codigos,
            string_to_array(ug_responsavel_nome, ', ') as nomes
        from {{ ref("convenio_mir") }}
        where ug_responsavel_codigo is not null
    ),

    posicoes as (
        select l.nr_convenio, c.codigo, l.nomes[c.posicao] as nome
        from listas as l
        cross join lateral unnest(l.codigos)
        with ordinality as c(codigo, posicao)
    ),

    pares as (
        select distinct
            nr_instrumento as nr_convenio, ug_responsavel_codigo, ug_responsavel_nome
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'SICONV'
    )

select nr_convenio, 'listas de tamanhos diferentes' as problema
from listas
where cardinality(codigos) <> cardinality(nomes)

union all

select p.nr_convenio, 'codigo e nome desalinhados' as problema
from posicoes as p
left join
    pares as r
    on r.nr_convenio = p.nr_convenio
    and r.ug_responsavel_codigo = p.codigo
    and r.ug_responsavel_nome = p.nome
where r.nr_convenio is null
