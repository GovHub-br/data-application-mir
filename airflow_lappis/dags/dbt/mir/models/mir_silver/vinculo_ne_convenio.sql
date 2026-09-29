{{ config(materialized="table") }}

-- Vinculo NE -> convenio do SICONV, no grao da NE.
-- Mesma regex de convenio usada hoje em numero_transferencia, mas aplicada a
-- TODAS as linhas de cada NE do ppa_tesouro (e nao so as de emendas): o
-- ne_info_complementar varia entre linhas da mesma NE. So contam candidatos
-- que existem no cadastro de convenios; mais de um candidato = NE ambigua.
with
    empenhos as (
        select ne_ccor, ne_info_complementar, ne_ccor_descricao, doc_observacao
        from {{ ref("ppa_tesouro") }}
        where ne_ccor <> '-9'
    ),

    padrao as (
        select
            '(?:CONVENIO|FOMENTO|FOMENO)\s*(?:N[°º]?)?\s*(\d{6})'::text as regex_convenio
    ),

    candidatos as (
        select
            ne_ccor,
            1 as prioridade,
            'info_complementar' as fonte,
            ne_info_complementar as nr_candidato
        from empenhos
        where ne_info_complementar ~ '^\d+$'

        union all

        select
            e.ne_ccor,
            2 as prioridade,
            'descricao' as fonte,
            (regexp_match(e.ne_ccor_descricao, p.regex_convenio, 'i'))[1] as nr_candidato
        from empenhos as e
        cross join padrao as p

        union all

        select
            e.ne_ccor,
            3 as prioridade,
            'observacao' as fonte,
            (regexp_match(e.doc_observacao, p.regex_convenio, 'i'))[1] as nr_candidato
        from empenhos as e
        cross join padrao as p
    ),

    convenios as (select distinct nr_convenio from {{ ref("convenio") }}),

    candidatos_validos as (
        select c.*
        from candidatos as c
        inner join convenios as v on v.nr_convenio = c.nr_candidato
    )

select
    ne_ccor,
    count(distinct nr_candidato) as qtd_convenios,
    case when count(distinct nr_candidato) = 1 then min(nr_candidato) end as nr_convenio,
    (array_agg(fonte order by prioridade))[1] as fonte_vinculo
from candidatos_validos
group by ne_ccor
