{{ config(materialized="table") }}

-- Agendas transversais e ODS (Blocos 3.1 e 3.2) a partir das agendas do PPA
-- do MIR. chave_agenda e estavel entre revisoes; vale o nome da revisao mais
-- recente.
select distinct
    on (chave_agenda)
    chave_agenda::text as codigo,
    nome_agenda::text as nome,
    grupo_agenda::text as grupo,
    nome_agenda_mae::text as nome_mae
from {{ ref("agenda_filtrado_mir") }}
where chave_agenda is not null
order by chave_agenda, ano_ppa desc
