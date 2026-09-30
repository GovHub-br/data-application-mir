{{ config(materialized="table") }}

-- Vinculo NE -> convenio do SICONV, no grao da NE.
-- Mesma regra de convenio do antigo numero_transferencia, mas aplicada a
-- TODAS as linhas de cada NE do ppa_tesouro (e nao so as de emendas): o
-- ne_info_complementar varia entre linhas da mesma NE. Aceita os numeros
-- numericos e os alfanumericos adotados a partir de 2026 (ex.: 7AACWU).
-- Fontes de candidatos, por prioridade: ne_info_complementar, rotulo explicito
-- "NUM. TRANSFERENCIA"/"SICONV" (descricao ou observacao), CONVENIO/FOMENTO na
-- descricao e na observacao (regex em macros/mir_silver/regex_vinculo.sql).
-- So contam candidatos que existem no cadastro de convenios. Com mais de um
-- candidato, desempata pelo numero de processo: vence o convenio cujo
-- nr_processo aparece em alguma linha da NE. Sem desempate = NE ambigua.
with
    empenhos as (
        select
            ne_ccor,
            ne_info_complementar,
            ne_ccor_descricao,
            doc_observacao,
            ne_num_processo
        from {{ ref("ppa_tesouro") }}
        where ne_ccor <> '-9'
    ),

    candidatos as (
        select
            ne_ccor,
            1 as prioridade,
            'info_complementar' as fonte,
            upper(ne_info_complementar) as nr_candidato
        from empenhos
        where ne_info_complementar ~* '^(\d+|\d[0-9A-Z]{5})$'

        union all

        select
            ne_ccor,
            2 as prioridade,
            'rotulo' as fonte,
            upper(
                (
                    regexp_match(
                        ne_ccor_descricao, {{ regex_rotulo_transferencia() }}, 'i'
                    )
                )[1]
            ) as nr_candidato
        from empenhos

        union all

        select
            ne_ccor,
            2 as prioridade,
            'rotulo' as fonte,
            upper(
                (regexp_match(doc_observacao, {{ regex_rotulo_transferencia() }}, 'i'))[1]
            ) as nr_candidato
        from empenhos

        union all

        select
            ne_ccor,
            3 as prioridade,
            'descricao' as fonte,
            upper(
                (regexp_match(ne_ccor_descricao, {{ regex_convenio() }}, 'i'))[1]
            ) as nr_candidato
        from empenhos

        union all

        select
            ne_ccor,
            4 as prioridade,
            'observacao' as fonte,
            upper(
                (regexp_match(doc_observacao, {{ regex_convenio() }}, 'i'))[1]
            ) as nr_candidato
        from empenhos
    ),

    convenios as (select distinct nr_convenio, nr_processo from {{ ref("convenio") }}),

    processos_ne as (
        select distinct ne_ccor, ne_num_processo
        from empenhos
        where ne_num_processo is not null
    ),

    -- Um candidato por NE x convenio: fonte de maior prioridade e se o
    -- processo do convenio aparece na NE
    candidatos_validos as (
        select
            c.ne_ccor,
            c.nr_candidato,
            (array_agg(c.fonte order by c.prioridade))[1] as fonte,
            bool_or(pn.ne_ccor is not null) as processo_bate
        from candidatos as c
        inner join convenios as v on v.nr_convenio = c.nr_candidato
        left join
            processos_ne as pn
            on pn.ne_ccor = c.ne_ccor
            and pn.ne_num_processo = v.nr_processo
        group by c.ne_ccor, c.nr_candidato
    ),

    por_ne as (
        select
            ne_ccor,
            count(*) as qtd_convenios,
            count(*) filter (where processo_bate) as qtd_convenios_processo
        from candidatos_validos
        group by ne_ccor
    ),

    escolhido as (
        select cv.ne_ccor, cv.nr_candidato, cv.fonte
        from candidatos_validos as cv
        inner join por_ne as n on n.ne_ccor = cv.ne_ccor
        where n.qtd_convenios = 1 or (n.qtd_convenios_processo = 1 and cv.processo_bate)
    )

select
    n.ne_ccor,
    n.qtd_convenios,
    e.nr_candidato as nr_convenio,
    e.fonte as fonte_vinculo,
    (n.qtd_convenios > 1 and e.nr_candidato is not null) as desempate_processo
from por_ne as n
left join escolhido as e on e.ne_ccor = n.ne_ccor
