{{ config(materialized="table") }}

with

    -- Base de estágios mensais, com CNPJ/CPF, processo e NE normalizados
    -- (mesmo tratamento aplicado em identificadores) para comparar com
    -- identificadores.
    estagios_base as (
        select
            *,
            upper(ne) as ne_transformed,
            regexp_replace(cnpj_cpf, '[^0-9]', '', 'g') as cnpj_cpf_transformed,
            regexp_replace(num_processo, '[^0-9]', '', 'g') as processo_transformed,
            info_complementar as info_complementar_transformed
        from {{ ref("estagios_mensal") }}
    ),

    -- Identificadores excluindo a categoria "Cessão": contratos de cessão não
    -- possuem execução financeira própria no SIAFI, então cruzá-los geraria
    -- falsos positivos em qualquer uma das 3 estratégias.
    identificadores_sem_cessao as (
        select
            contrato_id,
            ne,
            cnpj_cpf,
            processo,
            substring(info_complementar, '(^[0-9]+)') as info_complementar
        from {{ ref("identificadores") }}
        where categoria is distinct from 'Cessão'
    ),

    identificadores_com_ne as (
        select distinct contrato_id, ne, cnpj_cpf
        from identificadores_sem_cessao
        where ne is not null
    ),

    todos_identificadores as (
        select distinct contrato_id, processo, cnpj_cpf, info_complementar
        from identificadores_sem_cessao
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 1: left join por NE + CNPJ/CPF (chave mais confiável),
    -- excluindo identificadores da categoria "Cessão". Left join (e não
    -- full join, como em contratos_empenhos) porque aqui o grão de saída
    -- é o do estágio, não o do contrato: todo estágio é mantido, casado
    -- ou não, para seguir para as próximas estratégias da cascata.
    -- ------------------------------------------------------------------
    match_1 as (
        select e.*, i.contrato_id, 'ne_cnpj_cpf' as estrategia_match
        from estagios_base as e
        left join identificadores_com_ne as i
            on e.ne_transformed = i.ne and e.cnpj_cpf_transformed = i.cnpj_cpf
    ),

    resultado_1 as (
        select *
        from match_1
        where contrato_id is not null
    ),

    resolvidos_1 as (
        select distinct ne_transformed as ne, cnpj_cpf_transformed as cnpj_cpf
        from resultado_1
    ),

    estagios_restantes_1 as (
        select eb.*
        from estagios_base as eb
        left join resolvidos_1 as r1
            on eb.ne_transformed = r1.ne and eb.cnpj_cpf_transformed = r1.cnpj_cpf
        where r1.ne is null
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 2: join por CNPJ/CPF + processo, só quando essa combinação
    -- é única por contrato (evita fan-out quando o mesmo fornecedor e
    -- processo aparecem em mais de um contrato), restrito aos estágios
    -- ainda não resolvidos pela estratégia 1.
    -- ------------------------------------------------------------------
    cnpj_processo_unicos as (
        select distinct contrato_id, cnpj_cpf, processo
        from todos_identificadores
        where cnpj_cpf is not null and cnpj_cpf != ''
            and processo is not null and processo != ''
            and (cnpj_cpf, processo) in (
                select cnpj_cpf, processo
                from todos_identificadores
                where cnpj_cpf is not null and cnpj_cpf != ''
                    and processo is not null and processo != ''
                group by cnpj_cpf, processo
                having count(distinct contrato_id) = 1
            )
    ),

    resultado_2 as (
        select er.*, cpu.contrato_id, 'cnpj_cpf_processo' as estrategia_match
        from estagios_restantes_1 as er
        inner join cnpj_processo_unicos as cpu
            on er.cnpj_cpf_transformed = cpu.cnpj_cpf
            and er.processo_transformed = cpu.processo
    ),

    resolvidos_2 as (
        select distinct cnpj_cpf_transformed as cnpj_cpf, processo_transformed as processo
        from resultado_2
    ),

    estagios_restantes_2 as (
        select eb.*
        from estagios_restantes_1 as eb
        left join resolvidos_2 as r2
            on eb.cnpj_cpf_transformed = r2.cnpj_cpf
            and eb.processo_transformed = r2.processo
        where r2.cnpj_cpf is null
    ),

    -- ------------------------------------------------------------------
    -- Estratégia 3: join por CNPJ/CPF + info_complementar (UG + modalidade
    -- + número), só quando essa combinação é única por contrato, restrito
    -- aos estágios ainda não resolvidos pelas estratégias 1 e 2.
    -- ------------------------------------------------------------------
    cnpj_info_complementar_unicos as (
        select distinct contrato_id, cnpj_cpf, info_complementar
        from todos_identificadores
        where cnpj_cpf is not null and cnpj_cpf != ''
            and info_complementar is not null
            and (cnpj_cpf, info_complementar) in (
                select cnpj_cpf, info_complementar
                from todos_identificadores
                where cnpj_cpf is not null and cnpj_cpf != ''
                    and info_complementar is not null
                group by cnpj_cpf, info_complementar
                having count(distinct contrato_id) = 1
            )
    ),

    resultado_3 as (
        select er.*, cicu.contrato_id, 'cnpj_cpf_info_complementar' as estrategia_match
        from estagios_restantes_2 as er
        inner join cnpj_info_complementar_unicos as cicu
            on er.cnpj_cpf_transformed = cicu.cnpj_cpf
            and er.info_complementar_transformed = cicu.info_complementar
    ),

    -- União dos 3 resultados parciais. Cada estratégia só processa o que
    -- sobrou da anterior, então não há overlap real entre elas; o union
    -- (não union all) é só uma proteção defensiva contra linhas duplicadas
    -- idênticas.
    resultado_final as (
        select
            contrato_id,
            mes_lancamento,
            valor_empenhado,
            valor_liquidado,
            valor_pago,
            restos_a_pagar,
            restos_a_pagar_pago,
            estrategia_match,
            dt_ingest
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
            estrategia_match,
            dt_ingest
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
            estrategia_match,
            dt_ingest
        from resultado_3
    ),

    -- Agregação mensal por contrato: soma dos estágios de despesa de todos
    -- os empenhos casados com o mesmo contrato no mesmo mês.
    agregado_mensal as (
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
    coalesce(am.contrato_id, ca.id) as contrato_id,
    am.mes_lancamento,
    am.valor_empenhado,
    am.valor_liquidado,
    am.valor_pago,
    am.restos_a_pagar,
    am.restos_a_pagar_pago,
    am.estrategias_match,
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
    greatest(am.dt_ingest, ca.dt_ingest_contratos) as dt_ingest
from agregado_mensal as am
full join contratos_ativos as ca on am.contrato_id = ca.id
where ca.situacao = 'Ativo'
