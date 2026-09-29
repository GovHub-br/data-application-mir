{{ config(materialized="table") }}

{% set base_columns = [
    'emissao_mes', 'emissao_dia', 'codigo_programa', 'programa', 'codigo_acao_ajustada',
    'acao_ajustada', 'autor_emendas_orcamento_descricao', 'autor_emendas_orcamento_nome',
    'localizador_gasto', 'localizador_gasto_descricao', 'regiao_pt', 'uf', 'uf_descricao',
    'municipio', 'pais', 'ne_ccor', 'ne_num_processo', 'ne_info_complementar',
    'ne_ccor_descricao', 'doc_observacao', 'codigo_gnd', 'gnd', 'natureza_despesa',
    'natureza_despesa_descricao', 'codigo_modalidade', 'modalidade', 'ne_ccor_favorecido',
    'ne_ccor_favorecido_descricao', 'ne_ccor_ano_emissao', 'ptres', 'fonte_recursos_detalhada',
    'fonte_recursos_detalhada_descricao', 'dotacao_inicial', 'dotacao_atualizada',
    'despesas_empenhadas', 'despesas_liquidadas', 'despesas_pagas', 'restos_a_pagar_inscritos',
    'restos_a_pagar_pagos', 'autor_emendas_orcamento', 'ug_responsavel_codigo',
    'ug_responsavel_nome', 'id_autor', 'cargo_autor', 'autor', 'partido', 'uf_autor',
    'url_foto_autor', 'email_autor', 'url_foto_partido', 'dt_ingest'
] %}

with
    -- Extracao por linha: tenta achar o numero de transferencia no texto
    -- proprio de cada NE. Rotulo explicito ("NUM. TRANSFERENCIA"/"SICONV")
    -- vem antes de CONVENIO/FOMENTO/TED porque e mais especifico -- um texto
    -- pode citar "CONVENIO" apenas como parte do nome do proponente, sem
    -- numero nenhum logo em seguida, e nesse caso o CASE não deve parar
    -- ali sem tentar o rotulo mais confiavel. Ordem: campo 100% numerico,
    -- rotulo, CONVENIO/FOMENTO, TED -- cada um em ne_ccor_descricao e
    -- depois em doc_observacao.
    emendas as (
        select
            {{ star_except(base_columns) }},
            case
                when ne_info_complementar ~ '^\d+$'
                    then ne_info_complementar::integer
                when ne_ccor_descricao ~* 'NUM\.?\s*TRANSFERENCIA|SICONV'
                    then nullif(
                        regexp_replace(
                            ne_ccor_descricao,
                            '.*(?:NUM\.?\s*TRANSFERENCIA|SICONV)\s*:?\s*(\d{6}).*',
                            '\1'
                        ),
                        ne_ccor_descricao
                    )::integer
                when ne_ccor_descricao ~* 'CONVENIO|FOMENTO|FOMENO'
                    then nullif(
                        regexp_replace(
                            ne_ccor_descricao,
                            '.*(?:CONVENIO|FOMENTO|FOMENO)\s*(?:N[°º]?)?\s*(\d{6}).*',
                            '\1'
                        ),
                        ne_ccor_descricao
                    )::integer
                when ne_ccor_descricao ~* 'TED\s*\d{6}'
                    then nullif(
                        regexp_replace(
                            ne_ccor_descricao,
                            '.*TED\s*(\d{6}).*',
                            '\1'
                        ),
                        ne_ccor_descricao
                    )::integer
                when doc_observacao ~* 'NUM\.?\s*TRANSFERENCIA|SICONV'
                    then nullif(
                        regexp_replace(
                            doc_observacao,
                            '.*(?:NUM\.?\s*TRANSFERENCIA|SICONV)\s*:?\s*(\d{6}).*',
                            '\1'
                        ),
                        doc_observacao
                    )::integer
                when doc_observacao ~* 'CONVENIO|FOMENTO|FOMENO'
                    then nullif(
                        regexp_replace(
                            doc_observacao,
                            '.*(?:CONVENIO|FOMENTO|FOMENO)\s*(?:N[°º]?)?\s*(\d{6}).*',
                            '\1'
                        ),
                        doc_observacao
                    )::integer
                when doc_observacao ~* 'TED\s*\d{6}'
                    then nullif(
                        regexp_replace(
                            doc_observacao,
                            '.*TED\s*(\d{6}).*',
                            '\1'
                        ),
                        doc_observacao
                    )::integer
                else null
            end as numero_transferencia_texto
        from {{ ref("emendas_partidos") }}
    ),

    -- Backfill: a mesma NE (ne_ccor) aparece em varias linhas, uma por
    -- movimento/mes, e nem toda linha repete o texto com o numero de
    -- transferencia identificavel. Propaga o numero ja achado em qualquer
    -- linha da NE para as demais linhas da mesma NE.
    backfill_por_ne_ccor as (
        select
            ne_ccor,
            max(numero_transferencia_texto) as numero_transferencia_ne_ccor
        from emendas
        group by ne_ccor
    ),

    -- Cenario NSSALDO: empenho gerado pela rotina de transferencia de saldo
    -- nao carrega numero de transferencia proprio, mas referencia o
    -- "empenho de origem" (ex: "EMPENHO DE ORIGEM: 810008/2024NE000092") que
    -- carrega. Extrai a UG (6 digitos) e o sufixo ano+NE+sequencial
    -- (12 caracteres, mesmo recorte de right(ne_ccor, 12) usado em
    -- empenhos_por_plano_acao.sql) para cruzar com o ne_ccor da nota de
    -- origem.
    origem_referenciada as (
        select
            e.ne_ccor,
            m.origem_ug,
            m.origem_sufixo
        from emendas e
        cross join lateral (
            select
                (regexp_match(
                    coalesce(e.ne_ccor_descricao, ''),
                    '(?i)EMPENHO\s+DE\s+ORIGEM:\s*(\d{6})/(\d{4}NE\d{6})'
                ))[1] as origem_ug,
                (regexp_match(
                    coalesce(e.ne_ccor_descricao, ''),
                    '(?i)EMPENHO\s+DE\s+ORIGEM:\s*(\d{6})/(\d{4}NE\d{6})'
                ))[2] as origem_sufixo
        ) m
        where m.origem_ug is not null
    ),

    numero_transferencia_origem as (
        select
            o.ne_ccor,
            max(b.numero_transferencia_ne_ccor) as numero_transferencia_origem
        from origem_referenciada o
        join backfill_por_ne_ccor b
            on left(b.ne_ccor, 6) = o.origem_ug
            and right(b.ne_ccor, 12) = o.origem_sufixo
        where b.numero_transferencia_ne_ccor is not null
        group by o.ne_ccor
    )

select
    {{ star_except(base_columns, prefix='e.') }},
    coalesce(
        e.numero_transferencia_texto,
        b.numero_transferencia_ne_ccor,
        nto.numero_transferencia_origem
    ) as numero_transferencia
from emendas e
left join backfill_por_ne_ccor b on e.ne_ccor = b.ne_ccor
left join numero_transferencia_origem nto on e.ne_ccor = nto.ne_ccor
