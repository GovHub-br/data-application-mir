with

    parsed_estagios as (
        select
            right(ne_ccor, 12) as ne,
            emissao_mes as mes_lancamento,
            ne_ccor_favorecido as cnpj_cpf,
            substring(ne_info_complementar, '(^[0-9]+)') as info_complementar,
            ne_num_processo,
            despesas_empenhadas as valor_empenhado,
            despesas_liquidadas as valor_liquidado,
            despesas_pagas as valor_pago
        from {{ ref("empenhos_tesouro") }}
        where true and ne_ccor != 'Total' and emissao_mes not like '00%'
    ),

    grouped_estagios as (
        select
            ne,
            mes_lancamento,
            cnpj_cpf,
            max(info_complementar) as info_complementar,
            max(ne_num_processo) as num_processo,
            sum(valor_empenhado) as valor_empenhado,
            sum(valor_liquidado) as valor_liquidado,
            sum(valor_pago) as valor_pago
        from parsed_estagios
        group by 1, 2, 3
        order by 1, 2
    ),

    processo_fixed as (
        select
            ne,
            cnpj_cpf,
            info_complementar,
            {{ target.schema }}.parse_date(mes_lancamento) as mes_lancamento,
            min(num_processo) over (partition by ne) as num_processo,
            valor_empenhado,
            valor_liquidado,
            valor_pago
        from grouped_estagios
    ),

    cummulative_values as (
        select
            ne,
            cnpj_cpf,
            info_complementar,
            mes_lancamento,
            num_processo,
            valor_empenhado,
            valor_liquidado,
            valor_pago
        from processo_fixed
    )

--
select *
from cummulative_values
order by ne, cnpj_cpf, mes_lancamento
