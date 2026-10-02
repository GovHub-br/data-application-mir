-- Falha se uma meta, licitacao ou empenho de convenio do MIR aparecer
-- repetido na origem: as contagens e somas de convenio_contagens usam count(*)
-- e sum() e seriam infladas pela repeticao.
with
    mir as (select nr_convenio from {{ ref("convenio_mir") }}),

    repetidos as (
        select 'meta' as tipo, id_meta::text as id, count(*) as qtd
        from {{ ref("meta_crono_fisico") }}
        where nr_convenio in (select nr_convenio from mir)
        group by id_meta
        having count(*) > 1

        union all

        select 'licitacao' as tipo, id_licitacao::text as id, count(*) as qtd
        from {{ ref("licitacao") }}
        where nr_convenio in (select nr_convenio from mir)
        group by id_licitacao
        having count(*) > 1

        union all

        select 'empenho' as tipo, id_empenho::text as id, count(*) as qtd
        from {{ ref("empenho") }}
        where nr_convenio in (select nr_convenio from mir)
        group by id_empenho
        having count(*) > 1
    )

select *
from repetidos
