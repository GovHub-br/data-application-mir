{{ config(materialized="table") }}

-- Instrumentos que executam as emendas do MIR, uma linha por instrumento
-- registrado nas NEs de emenda do nucleo. Tipo pela modalidade do convenio do
-- MIR, TED pelo plano de acao, e "Convênio de outro órgão" para convenio do
-- SICONV fora do universo convenio_mir (NE do relatorio do MIR emitida por
-- outra UG; decisao do usuario em 2026-09-29). NEs sem instrumento ficam de
-- fora: no gold apontam para o membro -1 (Execucao direta / nao identificado).
with
    instrumentos as (
        select distinct sistema_instrumento, nr_instrumento
        from {{ ref("execucao_ne") }}
        where codigo_emenda is not null and sistema_instrumento <> 'Não identificado'
    ),

    outros_orgaos as (
        select
            c.nr_convenio,
            c.sit_convenio as situacao,
            p.objeto_proposta as objeto,
            p.nm_proponente as executor_nome
        from {{ ref("convenio") }} as c
        left join {{ ref("proposta") }} as p on p.id_proposta = c.id_proposta
        where
            c.nr_convenio in (
                select nr_instrumento
                from instrumentos
                where sistema_instrumento = 'SICONV'
            )
    )

select
    i.sistema_instrumento,
    i.nr_instrumento,
    case
        when i.sistema_instrumento = 'TED'
        then 'TED'
        when m.nr_convenio is null
        then 'Convênio de outro órgão'
        when m.modalidade = 'CONVENIO'
        then 'Convênio'
        when m.modalidade = 'TERMO DE FOMENTO'
        then 'Fomento'
        when m.modalidade = 'TERMO DE COLABORACAO'
        then 'Colaboração'
        when m.modalidade = 'TERMO DE PARCERIA'
        then 'Parceria'
    end as tipo_instrumento,
    coalesce(m.objeto, o.objeto, t.objeto) as objeto,
    coalesce(m.situacao, o.situacao, t.situacao) as situacao,
    coalesce(
        m.convenente_nome, o.executor_nome, t.unidade_descentralizada
    ) as executor_nome
from instrumentos as i
left join
    {{ ref("convenio_mir") }} as m
    on i.sistema_instrumento = 'SICONV'
    and m.nr_convenio = i.nr_instrumento
left join
    outros_orgaos as o
    on i.sistema_instrumento = 'SICONV'
    and m.nr_convenio is null
    and o.nr_convenio = i.nr_instrumento
left join
    {{ ref("ted_plano_acao") }} as t
    on i.sistema_instrumento = 'TED'
    and t.id_plano_acao::text = i.nr_instrumento
