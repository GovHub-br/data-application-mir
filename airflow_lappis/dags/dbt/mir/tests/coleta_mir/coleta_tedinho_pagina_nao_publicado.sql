{{ config(severity="warn") }}

-- Aviso (nao bloqueia): NC listada nas paginas de transparencia do gov.br
-- (ted_tedinho_gov_br) que nao chega a nenhum tedinho publicado em
-- coleta_instrumento (NC -> tedinhos_mir.instrumento_key -> 'tedinho:<chave>').
-- A pagina mescla instrumentos ('tedinho <A> / <B>', 'tedinho <A> + tedinho
-- <B>'); abre em NCs do mesmo jeito que coleta_instrumento.
with
    pagina_nc as (
        select pg.instrumento, partes.nc
        from {{ ref("ted_tedinho_gov_br") }} as pg
        cross join
            lateral unnest(
                regexp_split_to_array(replace(pg.instrumento, 'tedinho ', ''), ' (/|\+) ')
            ) as partes(nc)
    ),

    nc_chave as (
        select nc, instrumento_key::text as chave
        from {{ ref("tedinhos_mir") }}
        group by nc, instrumento_key
    )

select p.instrumento, p.nc
from pagina_nc as p
where
    not exists (
        select 1
        from nc_chave as k
        join {{ ref("coleta_instrumento") }} as c on c.chave = 'tedinho:' || k.chave
        where k.nc = p.nc
    )
