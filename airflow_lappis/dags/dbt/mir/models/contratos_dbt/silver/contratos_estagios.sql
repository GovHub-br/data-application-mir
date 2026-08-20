{{ config(materialized="table") }}

with

    -- Base de estágios mensais (já agregada por ne/cnpj_cpf/mês na silver
    -- estagios_mensal), com as colunas normalizadas para comparar com
    -- identificadores e um id sintético para rastrear o que já foi
    -- resolvido a cada etapa da cascata.
    estagios_base as (
        select
            *,
            row_number() over () as estagio_row_id,
            upper(ne) as ne_transformed,
            regexp_replace(cnpj_cpf, '[^0-9]', '', 'g') as cnpj_cpf_transformed,
            regexp_replace(num_processo, '[^0-9]', '', 'g') as processo_transformed
        from {{ ref("estagios_mensal") }}
    ),

    identificadores_com_ne as (
        select distinct contrato_id, ne, cnpj_cpf
        from {{ ref("identificadores") }}
        where ne is not null and categoria is distinct from 'Cessão'
    ),

    todos_identificadores as (
        select distinct
            contrato_id,
            cnpj_cpf,
            processo,
            substring(info_complementar, '(^[0-9]+)') as info_complementar
        from {{ ref("identificadores") }}
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 1: left join por NE + CNPJ/CPF (chave mais confiável),
    -- excluindo contratos de categoria "Cessão" do lado de identificadores.
    -- ------------------------------------------------------------------
    match_1 as (
        select i.contrato_id, e.*, 'ne_cnpj_cpf' as estrategia_match
        from estagios_base as e
        left join identificadores_com_ne as i
            on e.ne_transformed = i.ne and e.cnpj_cpf_transformed = i.cnpj_cpf
    ),

    resultado_1 as (
        select *
        from match_1
        where contrato_id is not null
    ),

    estagios_restantes_1 as (
        select *
        from estagios_base
        where estagio_row_id not in (select estagio_row_id from resultado_1)
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 2: para os não casados, join por CNPJ/CPF + processo.
    -- ------------------------------------------------------------------
    resultado_2 as (
        select ti.contrato_id, er.*, 'cnpj_cpf_processo' as estrategia_match
        from estagios_restantes_1 as er
        inner join todos_identificadores as ti
            on er.cnpj_cpf_transformed = ti.cnpj_cpf
            and er.processo_transformed = ti.processo
            and ti.processo is not null
            and ti.processo != ''
            and er.processo_transformed != ''
    ),

    estagios_restantes_2 as (
        select *
        from estagios_restantes_1
        where estagio_row_id not in (select estagio_row_id from resultado_2)
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 3: para os ainda não casados, join por
    -- CNPJ/CPF + info_complementar (prefixo numérico da UG).
    -- ------------------------------------------------------------------
    resultado_3 as (
        select ti.contrato_id, er.*, 'cnpj_cpf_info_complementar' as estrategia_match
        from estagios_restantes_2 as er
        inner join todos_identificadores as ti
            on er.cnpj_cpf_transformed = ti.cnpj_cpf
            and er.info_complementar = ti.info_complementar
            and ti.info_complementar is not null
    ),

    -- União dos 3 resultados parciais. Cada estratégia só processa o que
    -- sobrou da anterior, então não há overlap real de estagio_row_id
    -- entre elas; o union (não union all) é só uma proteção defensiva
    -- contra linhas duplicadas idênticas.
    resultado_final as (
        select
            contrato_id,
            mes_lancamento,
            valor_empenhado,
            valor_liquidado,
            valor_pago,
            restos_a_pagar,
            restos_a_pagar_pago,
            dt_ingest,
            estrategia_match
        from resultado_1
        union
        select
            contrato_id,
            mes_lancamento,
            valor_empenhado,
            valor_liquidado,
            valor_pago,
            restos_a_pagar,
            restos_a_pagar_pago,
            dt_ingest,
            estrategia_match
        from resultado_2
        union
        select
            contrato_id,
            mes_lancamento,
            valor_empenhado,
            valor_liquidado,
            valor_pago,
            restos_a_pagar,
            restos_a_pagar_pago,
            dt_ingest,
            estrategia_match
        from resultado_3
    ),

    -- Agregação mensal por contrato_id + mes_lancamento.
    agregado as (
        select
            contrato_id,
            mes_lancamento,
            sum(valor_empenhado) as valor_empenhado,
            sum(valor_liquidado) as valor_liquidado,
            sum(valor_pago) as valor_pago,
            sum(restos_a_pagar) as restos_a_pagar,
            sum(restos_a_pagar_pago) as restos_a_pagar_pago,
            array_agg(distinct estrategia_match) as estrategias_match,
            max(dt_ingest) as dt_ingest
        from resultado_final
        group by contrato_id, mes_lancamento
    ),

    contratos_ativos as (
        select
            id,
            numero,
            situacao,
            fornecedor_tipo,
            fornecedor_nome,
            fornecedor_cnpj_cpf_idgener,
            objeto,
            unidades_requisitantes,
            vigencia_inicio,
            vigencia_fim,
            contratante__orgao__nome as orgao_contratante,
            contratante__orgao__unidade_gestora__nome as unidade_gestora,
            dt_ingest as dt_ingest_contratos
        from {{ ref("contratos") }}
    )

select
    coalesce(ag.contrato_id, ca.id) as contrato_id,
    ag.mes_lancamento,
    ag.valor_empenhado,
    ag.valor_liquidado,
    ag.valor_pago,
    ag.restos_a_pagar,
    ag.restos_a_pagar_pago,
    ag.estrategias_match,
    ca.numero as numero_contrato,
    ca.situacao as situacao_contrato,
    ca.fornecedor_nome,
    ca.fornecedor_cnpj_cpf_idgener,
    ca.orgao_contratante,
    ca.unidade_gestora,
    ca.objeto as objeto_contrato,
    ca.unidades_requisitantes,
    ca.vigencia_inicio,
    ca.vigencia_fim,
    greatest(ag.dt_ingest, ca.dt_ingest_contratos) as dt_ingest
from agregado as ag
full join contratos_ativos as ca on ag.contrato_id = ca.id
where ca.situacao = 'Ativo'
