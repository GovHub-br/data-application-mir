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
            from {{ ref("planos_acao_ted") }} pa
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
            sum(
                case
                    when nc_evento in ('300301', '300307') then 0
                    else valor_celula
                end
            ) as orcamento_recebido,
            sum(
                case
                    when nc_evento in ('300301', '300307') then valor_celula
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

    valores_empenhados_tb as (
        select
            ltrim(trim(cast(num_transf as text)), '0') as num_transf_canon,
            ug_responsavel_codigo,
            ug_responsavel_nome,
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
        group by
            ltrim(trim(cast(num_transf as text)), '0'),
            ug_responsavel_codigo,
            ug_responsavel_nome
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
    -- ponte plano_por_transf. A dimensao ug_responsavel vem apenas dos empenhos,
    -- entao os demais blocos (orcamento/financeiro/valor firmado) se repetem
    -- entre as linhas de ug de uma mesma transferencia — comportamento herdado
    -- da granularidade ug adicionada em modelos anteriores, preservado aqui.
    join_parcial as (
        select
            num_transf_canon,
            ve.ug_responsavel_codigo,
            ve.ug_responsavel_nome,
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
    )

select
    ppt.plano_acao,
    jp.num_transf_canon as num_transf,
    jp.ug_responsavel_codigo,
    jp.ug_responsavel_nome,
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
