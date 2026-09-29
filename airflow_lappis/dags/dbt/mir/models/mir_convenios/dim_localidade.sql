-- Municipio do convenente (codigo IBGE), com UF e regiao. Convenio sem
-- municipio fica numa linha so com a UF (chave 'UF-<sigla>').
with
    locais as (
        select distinct on (chave_localidade) *
        from
            (
                select
                    coalesce(cod_municipio_ibge, 'UF-' || uf) as chave_localidade,
                    cod_municipio_ibge,
                    municipio,
                    uf
                from {{ ref("convenio_mir") }}
                where coalesce(cod_municipio_ibge, uf) is not null
            ) as l
        order by chave_localidade, municipio
    )

select
    {{ surrogate_key(["l.chave_localidade"]) }} as sk_localidade,
    l.chave_localidade,
    l.cod_municipio_ibge,
    coalesce(l.municipio, 'Não informado') as municipio,
    l.uf,
    r.nome_uf,
    r.regiao
from locais as l
left join {{ ref("uf_regiao") }} as r on r.uf = l.uf

union all

select
    -1::bigint,
    '-1',
    null,
    'Não identificado',
    null,
    'Não identificado',
    'Não identificado'
