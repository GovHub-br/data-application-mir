{{ config(materialized="table") }}

with

    -- Base de empenhos (já filtrada por UG do MIR na bronze empenhos_tesouro)
    -- com as colunas normalizadas para comparar com identificadores.
    empenhos_base as (
        select
            *,
            upper(right(ne_ccor, 12)) as ne_transformed,
            regexp_replace(ne_ccor_favorecido, '[^0-9]', '', 'g') as cnpj_cpf_transformed,
            regexp_replace(ne_num_processo, '[^0-9]', '', 'g') as processo_transformed,
            substring(ne_info_complementar, '(^[0-9]+)') as info_complementar_transformed
        from {{ ref("empenhos_tesouro") }}
        where ne_ccor != 'Total'
    ),

    identificadores_com_ne as (
        select distinct contrato_id, ne, cnpj_cpf
        from {{ ref("identificadores") }}
        where ne is not null
    ),

    todos_identificadores as (
        select distinct contrato_id, processo, cnpj_cpf, info_complementar
        from {{ ref("identificadores") }}
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 1: full join por NE + CNPJ/CPF (chave mais confiável)
    -- ------------------------------------------------------------------
    match_1 as (
        select i.contrato_id, e.*, 'ne_cnpj_cpf' as estrategia_match
        from identificadores_com_ne as i
        full join empenhos_base as e
            on i.ne = e.ne_transformed
            and i.cnpj_cpf = e.cnpj_cpf_transformed
    ),

    resultado_1 as (
        select *
        from match_1
        where contrato_id is not null and ne_ccor is not null
    ),

    empenhos_restantes_1 as (
        select *
        from empenhos_base
        where ne_ccor not in (select ne_ccor from resultado_1)
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 2: join por processo, só quando o processo é único por
    -- contrato (evita fan-out de um mesmo processo em vários contratos).
    -- ------------------------------------------------------------------
    processos_unicos as (
        select distinct contrato_id, processo
        from todos_identificadores
        where processo is not null and processo != ''
            and processo in (
                select processo
                from todos_identificadores
                where processo is not null and processo != ''
                group by processo
                having count(distinct contrato_id) = 1
            )
    ),

    resultado_2 as (
        select pu.contrato_id, er.*, 'processo_unico' as estrategia_match
        from empenhos_restantes_1 as er
        inner join processos_unicos as pu on er.processo_transformed = pu.processo
    ),

    empenhos_restantes_2 as (
        select *
        from empenhos_restantes_1
        where ne_ccor not in (select ne_ccor from resultado_2)
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 3: join por cnpj_cpf, só quando o CNPJ/CPF é único por
    -- contrato.
    -- ------------------------------------------------------------------
    cnpjs_unicos as (
        select distinct contrato_id, cnpj_cpf
        from todos_identificadores
        where cnpj_cpf is not null and cnpj_cpf != ''
            and cnpj_cpf in (
                select cnpj_cpf
                from todos_identificadores
                where cnpj_cpf is not null and cnpj_cpf != ''
                group by cnpj_cpf
                having count(distinct contrato_id) = 1
            )
    ),

    resultado_3 as (
        select cu.contrato_id, er.*, 'cnpj_cpf_unico' as estrategia_match
        from empenhos_restantes_2 as er
        inner join cnpjs_unicos as cu on er.cnpj_cpf_transformed = cu.cnpj_cpf
    ),

    empenhos_restantes_3 as (
        select *
        from empenhos_restantes_2
        where ne_ccor not in (select ne_ccor from resultado_3)
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 4: join pelo prefixo numérico (UG) de info_complementar,
    -- só quando esse prefixo é único por contrato. O SIAFI não garante
    -- formato parseável além da UG em ne_info_complementar, então esta é
    -- a estratégia mais fraca da cascata; com apenas 2 UGs no MIR, a
    -- restrição de unicidade deve deixá-la resolver pouco ou nada — isso
    -- é esperado, não um problema de implementação.
    -- ------------------------------------------------------------------
    info_complementar_unicos as (
        select distinct
            contrato_id, substring(info_complementar, '(^[0-9]+)') as info_complementar
        from todos_identificadores
        where info_complementar is not null
            and substring(info_complementar, '(^[0-9]+)') in (
                select substring(info_complementar, '(^[0-9]+)')
                from todos_identificadores
                where info_complementar is not null
                group by 1
                having count(distinct contrato_id) = 1
            )
    ),

    resultado_4 as (
        select icu.contrato_id, er.*, 'info_complementar_unico' as estrategia_match
        from empenhos_restantes_3 as er
        inner join info_complementar_unicos as icu
            on er.info_complementar_transformed = icu.info_complementar
    ),

    -- União dos 4 resultados parciais. Cada estratégia só processa o que
    -- sobrou da anterior, então não há overlap real de ne_ccor entre elas;
    -- o union (não union all) é só uma proteção defensiva contra linhas
    -- duplicadas idênticas.
    resultado_final as (
        select
            contrato_id,
            ne_ccor,
            ne_transformed,
            ne_num_processo,
            ne_info_complementar,
            natureza_despesa,
            natureza_despesa_descricao,
            ne_ccor_favorecido,
            ne_ccor_ano_emissao,
            despesas_empenhadas,
            despesas_liquidadas,
            despesas_pagas,
            dt_ingest,
            estrategia_match
        from resultado_1
        union
        select
            contrato_id,
            ne_ccor,
            ne_transformed,
            ne_num_processo,
            ne_info_complementar,
            natureza_despesa,
            natureza_despesa_descricao,
            ne_ccor_favorecido,
            ne_ccor_ano_emissao,
            despesas_empenhadas,
            despesas_liquidadas,
            despesas_pagas,
            dt_ingest,
            estrategia_match
        from resultado_2
        union
        select
            contrato_id,
            ne_ccor,
            ne_transformed,
            ne_num_processo,
            ne_info_complementar,
            natureza_despesa,
            natureza_despesa_descricao,
            ne_ccor_favorecido,
            ne_ccor_ano_emissao,
            despesas_empenhadas,
            despesas_liquidadas,
            despesas_pagas,
            dt_ingest,
            estrategia_match
        from resultado_3
        union
        select
            contrato_id,
            ne_ccor,
            ne_transformed,
            ne_num_processo,
            ne_info_complementar,
            natureza_despesa,
            natureza_despesa_descricao,
            ne_ccor_favorecido,
            ne_ccor_ano_emissao,
            despesas_empenhadas,
            despesas_liquidadas,
            despesas_pagas,
            dt_ingest,
            estrategia_match
        from resultado_4
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
    coalesce(rf.contrato_id, ca.id) as contrato_id,
    rf.ne_transformed as ne,
    rf.ne_ccor,
    rf.ne_num_processo,
    rf.ne_info_complementar,
    rf.natureza_despesa,
    rf.natureza_despesa_descricao,
    rf.ne_ccor_favorecido as cnpj_cpf_favorecido,
    rf.ne_ccor_ano_emissao,
    rf.despesas_empenhadas,
    rf.despesas_liquidadas,
    rf.despesas_pagas,
    rf.estrategia_match,
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
    greatest(rf.dt_ingest, ca.dt_ingest_contratos) as dt_ingest
from resultado_final as rf
full join contratos_ativos as ca on rf.contrato_id = ca.id
where ca.situacao = 'Ativo'
