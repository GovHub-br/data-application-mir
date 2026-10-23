{{ config(materialized="table") }}

-- Agendas transversais e ODS (Blocos 3.1 e 3.2) a partir das agendas do PPA
-- do MIR. chave_agenda e estavel entre revisoes; vale o nome da revisao mais
-- recente em que a agenda aparece. in_vigente: a agenda aparece na revisao
-- mais recente do PPA (mesma revisao de coleta_lista_ppa).
with
    revisao as (select max(ano_ppa) as ano_ppa from {{ ref("programa_filtrado_mir") }}),

    agenda as (
        select distinct
            on (chave_agenda)
            chave_agenda::text as codigo,
            nome_agenda::text as nome,
            grupo_agenda::text as grupo,
            nome_agenda_mae::text as nome_mae,
            ano_ppa
        from {{ ref("agenda_filtrado_mir") }}
        where chave_agenda is not null
        order by chave_agenda, ano_ppa desc
    )

select
    a.codigo,
    a.nome,
    a.grupo,
    a.nome_mae,
    coalesce(a.ano_ppa = r.ano_ppa, false) as in_vigente
from agenda as a
cross join revisao as r
