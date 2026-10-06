{{ config(materialized="table") }}

with
    planos_acao_deduplicado as (
        select
            id_plano_acao,
            id_programa,
            sq_instrumento as num_transf,
            sigla_unidade_descentralizada,
            vl_total_plano_acao,
            dt_ingest as dt_ingest_plano_acao
        from (
            select
                pa.*,
                row_number() over (
                    partition by pa.id_plano_acao
                    order by pa.dt_ingest desc
                ) as rn
            -- portal do sistema TED, com a API de dados abertos como reserva
            from {{ ref("ted_plano_acao_consolidado") }} pa
        ) pa_filtrado
        where rn = 1
    ),

    programas_tb as (
        select
            pad.id_plano_acao,
            prog.sigla_unidade_responsavel_acompanhamento,
            prog.tx_nome_institucional_programa,
            prog.tx_objetivo_programa
        from planos_acao_deduplicado pad
        left join {{ ref("programas_ted") }} prog using (id_programa)
    ),

    -- Ponte canonica num_transf -> plano_acao. num_transf_n_plano_acao ja e
    -- 1:1 por transferencia; deduplicamos defensivamente por num_transf_canon
    -- (row_number) para que o join de resolucao do plano nunca reintroduza
    -- fan-out mesmo que a fonte venha a ter mais de um plano por transferencia.
    plano_por_transf as (
        select num_transf_canon, plano_acao::integer as plano_acao
        from (
            select
                ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
                plano_acao,
                row_number() over (
                    partition by ltrim(trim(cast(num_transf as text)), '0')
                    order by plano_acao
                ) as rn
            from {{ ref("num_transf_n_plano_acao") }}
            where num_transf is not null
        ) t
        where rn = 1
    ),

    valor_firmado_tb as (
        select
            ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
            max(vl_total_plano_acao) as valor_firmado,
            max(sigla_unidade_descentralizada) as sigla_unidade_descentralizada,
            max(dt_ingest_plano_acao) as dt_ingest_vf
        from planos_acao_deduplicado
        where num_transf is not null
            and ltrim(trim(cast(num_transf as text)), '0') <> ''
        group by ltrim(trim(cast(num_transf as text)), '0')
    ),

    valores_orcamentos_tb as (
        select
            ltrim(trim(cast(nc_transferencia as text)), '0') as num_transf_canon,
            -- valor_celula e sempre positivo; o sentido vem do tipo da NC. A
            -- anulacao desfaz parte da descentralizacao e abate o recebido.
            sum(
                case
                    when nc_evento_descricao ~* '^DESC' then valor_celula
                    when nc_evento_descricao ~* '^ANU' then -valor_celula
                    else 0
                end
            ) as orcamento_recebido,
            sum(
                case
                    when nc_evento_descricao ~* '^DEV' then valor_celula
                    else 0
                end
            ) as orcamento_devolvido,
            max(programa_governo) as programa_governo,
            max(programa_governo_descricao) as programa_governo_descricao,
            max(dt_ingest) as dt_ingest_vo
        from {{ ref("nc_plano_acao") }}
        where ptres not in ('-9')
            and nc_transferencia is not null
            and ltrim(trim(cast(nc_transferencia as text)), '0') <> ''
        group by ltrim(trim(cast(nc_transferencia as text)), '0')
    ),

    -- Agregado no grao da transferencia canonica, igual aos demais blocos. A UG
    -- responsavel NAO entra no group by: quando estava na chave, a transferencia
    -- com N UGs virava N linhas e os blocos de valor firmado, orcamento e
    -- financeiro — que so existem no grao da transferencia — eram repetidos em
    -- cada linha, inflando qualquer soma (ate +18% nos totais). As UGs viram
    -- atributo consolidado; o detalhe por UG vive em ted_empenhos_plano_acao.
    valores_empenhados_tb as (
        select
            ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
            string_agg(
                distinct cast(ug_responsavel_codigo as text),
                ', '
                order by cast(ug_responsavel_codigo as text)
            ) as ugs_responsaveis_codigos,
            string_agg(
                distinct ug_responsavel_nome, ', ' order by ug_responsavel_nome
            ) as ugs_responsaveis_nomes,
            count(distinct ug_responsavel_codigo) as qtd_ugs_responsaveis,
            sum(
                case when despesas_empenhadas > 0 then despesas_empenhadas else 0 end
            ) as empenhado,
            sum(
                case when despesas_empenhadas < 0 then -despesas_empenhadas else 0 end
            ) as empenho_anulado,
            sum(despesas_pagas) as despesas_pagas_exercicio,
            sum(restos_a_pagar_pagos) as despesas_pagas_rap,
            sum(restos_a_pagar_inscritos) as restos_a_pagar,
            sum(despesas_liquidadas) as despesas_liquidada,
            max(dt_ingest) as dt_ingest_ve
        from {{ ref("empenhos_por_plano_acao") }}
        where num_transf is not null
            and ltrim(trim(cast(num_transf as text)), '0') <> ''
        group by ltrim(trim(cast(num_transf as text)), '0')
    ),

    valores_financeiro_tb as (
        select
            ltrim(trim(cast(pf_inscricao as text)), '0') as num_transf_canon,
            sum(
                case
                    when substring(pf_acao_descricao, '(\w+) ') = 'TRANSFERENCIA'
                    then pf_valor_linha
                    else 0
                end
            ) as financeiro_recebido,
            sum(
                case
                    when substring(pf_acao_descricao, '(\w+) ') = 'DEVOLUCAO'
                    then pf_valor_linha
                    else 0
                end
            ) as financeiro_devolvido,
            sum(
                case
                    when substring(pf_acao_descricao, '(\w+) ') = 'CANCELAMENTO'
                    then pf_valor_linha
                    else 0
                end
            ) as financeiro_cancelado,
            max(dt_ingest) as dt_ingest_vfin
        from {{ ref("pf_unificado") }}
        where pf_inscricao is not null
            and ltrim(trim(cast(pf_inscricao as text)), '0') <> ''
        group by ltrim(trim(cast(pf_inscricao as text)), '0')
    ),

    emendas as (
        -- numero_transferencia vem no grao NE x mes x movimento (varias linhas por
        -- transferencia). Agregamos ao grao de transferencia canonica para nao
        -- introduzir fan-out no join final: o resumo so precisa saber se ha emenda
        -- e quais autores, entao consolidamos preservando os autores sem multiplicar
        -- linhas.
        select
            ltrim(trim(cast(numero_transferencia as text)), '0') as num_transf_canon,
            bool_or(id_autor is not null) as tem_autor,
            string_agg(
                distinct autor_emendas_orcamento::text, ', '
                order by autor_emendas_orcamento::text
            ) filter (where id_autor is not null) as autor_emendas_orcamento
        from {{ ref("numero_transferencia") }}
        where numero_transferencia is not null
        group by ltrim(trim(cast(numero_transferencia as text)), '0')
    ),

    -- Consolidacao dos quatro blocos por num_transf_canon (a transferencia e a
    -- unica chave de juncao). plano_acao NAO entra na chave: era a causa do join
    -- estrutural quebrado (NULL nao casa com NULL) e e resolvido depois via a
    -- ponte plano_por_transf. Os quatro blocos estao todos no grao da
    -- transferencia, entao o join e 1:1 e nenhuma metrica e duplicada.
    join_parcial as (
        select
            num_transf_canon,
            ve.ugs_responsaveis_codigos,
            ve.ugs_responsaveis_nomes,
            ve.qtd_ugs_responsaveis,
            vf.valor_firmado,
            vf.sigla_unidade_descentralizada,
            vo.orcamento_recebido,
            vo.orcamento_devolvido,
            vo.programa_governo,
            vo.programa_governo_descricao,
            ve.empenhado,
            ve.empenho_anulado,
            ve.despesas_pagas_exercicio,
            ve.despesas_pagas_rap,
            ve.restos_a_pagar,
            ve.despesas_liquidada,
            vfin.financeiro_recebido,
            vfin.financeiro_devolvido,
            vfin.financeiro_cancelado,
            greatest(
                vf.dt_ingest_vf, vo.dt_ingest_vo, ve.dt_ingest_ve, vfin.dt_ingest_vfin
            ) as dt_ingest_jp
        from valores_empenhados_tb ve
        full join valores_orcamentos_tb vo using (num_transf_canon)
        full join valores_financeiro_tb vfin using (num_transf_canon)
        full join valor_firmado_tb vf using (num_transf_canon)
    ),

    teds as (
        select
            ppt.plano_acao,
            'TED' as tipo_instrumento,
            jp.num_transf_canon as num_transf,
            cast(null as text) as processo,
            jp.ugs_responsaveis_codigos,
            jp.ugs_responsaveis_nomes,
            jp.qtd_ugs_responsaveis,
            jp.sigla_unidade_descentralizada,
            jp.valor_firmado,
            jp.orcamento_recebido,
            jp.orcamento_devolvido,
            jp.empenhado,
            jp.empenho_anulado,
            jp.despesas_pagas_exercicio,
            jp.despesas_pagas_rap,
            jp.restos_a_pagar,
            jp.despesas_liquidada,
            jp.financeiro_recebido,
            jp.financeiro_devolvido,
            jp.financeiro_cancelado,
            jp.dt_ingest_jp as dt_ingest,
            prog.sigla_unidade_responsavel_acompanhamento,
            prog.tx_nome_institucional_programa,
            prog.tx_objetivo_programa,
            jp.programa_governo,
            jp.programa_governo_descricao,
            case when e.tem_autor then 'Emenda - ' || e.autor_emendas_orcamento else 'Recurso Próprio' end as origem
        from join_parcial jp
        left join plano_por_transf ppt using (num_transf_canon)
        left join programas_tb prog on prog.id_plano_acao = ppt.plano_acao
        left join emendas e using (num_transf_canon)
        where jp.num_transf_canon is not null
    ),

    -- Tedinhos (issue #507): descentralizacoes de credito que nunca chegam a
    -- ser registradas no TransfereGov -- ver tedinhos_mir.sql para a regra de
    -- deteccao. Viram instrumento proprio aqui, chaveado por instrumento_key
    -- (nc_transferencia quando atribuido, senao processo, senao a propria NC
    -- -- nunca existe num_transf nem plano_acao reconhecido, por definicao).
    -- A coluna processo exposta aqui e o melhor identificador humano
    -- disponivel: processo administrativo (2026+) ou, quando so existe o
    -- codigo interno do SIAFI (anos sem processo extraivel), esse codigo.
    -- Empenhado/liquidado/pago/valor_firmado ficam nulos: a NE do orgao
    -- executor carrega o *proprio* processo administrativo dele, nao o do
    -- MIR, entao nao ha hoje um join confiavel entre o tedinho e
    -- empenhos_por_plano_acao (confirmado: 0 de 23 processos conhecidos
    -- batem via ne_num_processo). Resolver essa lacuna exige uma fonte
    -- adicional (ex. de-para processo MIR -> processo da instituicao
    -- executora) fora do escopo desta mudanca.
    tedinhos as (
        select
            cast(null as integer) as plano_acao,
            'Tedinho' as tipo_instrumento,
            cast(null as text) as num_transf,
            coalesce(
                max(processo), nullif(max(nc_transferencia_atual), '-8'), max(nc)
            ) as processo,
            cast(null as text) as ugs_responsaveis_codigos,
            cast(null as text) as ugs_responsaveis_nomes,
            cast(null as bigint) as qtd_ugs_responsaveis,
            cast(null as text) as sigla_unidade_descentralizada,
            cast(null as numeric) as valor_firmado,
            sum(
                case
                    when nc_evento_descricao ilike '%DEVOLUCAO%'
                        or nc_evento_descricao ilike '%ANULACAO%'
                    then 0
                    else valor_celula
                end
            ) as orcamento_recebido,
            sum(
                case
                    when nc_evento_descricao ilike '%DEVOLUCAO%'
                        or nc_evento_descricao ilike '%ANULACAO%'
                    then valor_celula
                    else 0
                end
            ) as orcamento_devolvido,
            cast(null as numeric) as empenhado,
            cast(null as numeric) as empenho_anulado,
            cast(null as numeric) as despesas_pagas_exercicio,
            cast(null as numeric) as despesas_pagas_rap,
            cast(null as numeric) as restos_a_pagar,
            cast(null as numeric) as despesas_liquidada,
            cast(null as numeric) as financeiro_recebido,
            cast(null as numeric) as financeiro_devolvido,
            cast(null as numeric) as financeiro_cancelado,
            max(dt_ingest) as dt_ingest,
            cast(null as text) as sigla_unidade_responsavel_acompanhamento,
            cast(null as text) as tx_nome_institucional_programa,
            cast(null as text) as tx_objetivo_programa,
            cast(null as text) as programa_governo,
            cast(null as text) as programa_governo_descricao,
            'Tedinho (sem registro no TransfereGov)' as origem
        from {{ ref("tedinhos_mir") }}
        where tedinho_provavel
        group by instrumento_key
    )

select * from teds
union all
select * from tedinhos
