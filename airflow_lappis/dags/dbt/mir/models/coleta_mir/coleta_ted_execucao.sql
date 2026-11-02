{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, Bloco 1 do formulário de TEDs ("Valor empenhado" e "Valor
  liquidado / pago"): uma linha por TED de coleta_ted. Fica fora de coleta_ted para uma
  falha na cadeia do SIAFI não travar os dados de identificação.

  Cada TED fica com a primeira origem que o resolve (ds_origem_execucao):
    consulta_oficial  está em ted_execucao_por_instrumento, a consulta oficial "Execução
                      TED por UG" aberta por instrumento.
    sem_dado          é anterior ao primeiro exercício da consulta, ou divide célula com
                      outro TED (abaixo). Valores nulos: não dá para dizer quanto foi.
    nota_de_empenho   a consulta só traz EOF primário discricionário e deixa de fora TED
                      de emenda e UG fora do recorte (ex.: ABC). Soma as NEs da célula
                      (UG favorecida da NC, PTRES) do TED.
    sem_empenho       nenhuma NE na célula, ou a soma delas é zero. Valores 0.

  Instrumento mesclado da gold ("A + B") é a junção que o crédito não permite separar.
  Não se rateia: fica fora de vl_empenhado e vl_pago dos TEDs e aparece inteiro em cada
  um nas colunas de compartilhado.

  Não converte moeda: as NEs da UG 364150 do CNPq estão em dólar em 2023-25 até a
  reextração no Tesouro Gerencial (ver a descrição de vl_empenhado).
#}
with
    gold as (
        select instrumento, empenhado, pago_total
        from {{ ref("ted_execucao_por_instrumento") }}
        where tipo_instrumento = 'TED'
    ),

    oficial as (
        select
            instrumento as nr_transferencia,
            sum(empenhado) as vl_empenhado,
            sum(pago_total) as vl_pago
        from gold
        where instrumento not like '% + %'
        group by instrumento
    ),

    compartilhado as (
        select
            p.parte as nr_transferencia,
            sum(m.empenhado) as vl_empenhado,
            sum(m.pago_total) as vl_pago,
            string_agg(distinct m.instrumento, '; ') as ds_instrumento
        from gold as m
        cross join lateral unnest(string_to_array(m.instrumento, ' + ')) as p(parte)
        where m.instrumento like '% + %'
        group by p.parte
    ),

    -- Células das NCs dos TEDs fora da gold, com o ano da primeira NC.
    celula as (
        select
            c.id_plano_acao,
            n.favorecido_doc as ug,
            n.ptres,
            min(n.emissao_ano::integer) as aa_primeira_nc,
            count(*) over (partition by n.favorecido_doc, n.ptres) as teds_na_celula
        from {{ ref("coleta_ted") }} as c
        join {{ ref("nc_unificado") }} as n on n.nc_transferencia = c.nr_transferencia
        where
            n.relatorio = 'enviadas'
            and c.nr_transferencia not in (select nr_transferencia from oficial)
            and c.nr_transferencia not in (select nr_transferencia from compartilhado)
        group by c.id_plano_acao, n.favorecido_doc, n.ptres
    ),

    -- Só exercício a partir da primeira NC: a mesma célula pode ter NEs mais antigas de
    -- outro instrumento. As NEs que a consulta oficial já traz não entram, para não
    -- contar duas vezes. ne_ccor = '-9' são as linhas de dotação.
    nota_de_empenho as (
        select
            c.id_plano_acao,
            sum(p.despesas_empenhadas) as vl_empenhado,
            sum(p.despesas_pagas + p.restos_a_pagar_pagos) as vl_pago
        from celula as c
        join
            {{ ref("ppa_tesouro") }} as p
            on left(p.ne_ccor, 6) = c.ug
            and p.ptres = c.ptres
        where
            c.teds_na_celula = 1
            and p.ne_ccor <> '-9'
            and right(p.emissao_mes, 4)::integer >= c.aa_primeira_nc
            and not exists (
                select 1
                from {{ ref("execucao_ted_ne_vinculo") }} as v
                where v.ne_ccor = p.ne_ccor
            )
        group by c.id_plano_acao
    ),

    credito as (
        select id_plano_acao, sum(vl_liquido) as vl_liquido
        from {{ ref("coleta_ted_fonte") }}
        group by id_plano_acao
    ),

    execucao as (
        select
            c.id_plano_acao,
            coalesce(o.vl_empenhado, n.vl_empenhado, 0) as vl_empenhado,
            coalesce(o.vl_pago, n.vl_pago, 0) as vl_pago,
            s.vl_empenhado as vl_empenhado_compartilhado,
            s.vl_pago as vl_pago_compartilhado,
            s.ds_instrumento as ds_instrumento_compartilhado,
            case
                when o.nr_transferencia is not null or s.nr_transferencia is not null
                then 'consulta_oficial'
                when
                    c.aa_instrumento
                    < (select min(ano) from {{ ref("ted_execucao_por_instrumento") }})
                    or c.id_plano_acao
                    in (select id_plano_acao from celula where teds_na_celula > 1)
                then 'sem_dado'
                when n.vl_empenhado <> 0 or n.vl_pago <> 0
                then 'nota_de_empenho'
                else 'sem_empenho'
            end as ds_origem_execucao
        from {{ ref("coleta_ted") }} as c
        left join oficial as o on o.nr_transferencia = c.nr_transferencia
        left join compartilhado as s on s.nr_transferencia = c.nr_transferencia
        left join nota_de_empenho as n on n.id_plano_acao = c.id_plano_acao
    )

select
    e.id_plano_acao::integer as id_plano_acao,
    case
        when e.ds_origem_execucao <> 'sem_dado' then e.vl_empenhado::numeric(15, 2)
    end as vl_empenhado,
    case
        when e.ds_origem_execucao <> 'sem_dado' then e.vl_pago::numeric(15, 2)
    end as vl_pago,
    cr.vl_liquido::numeric(15, 2) as vl_credito_liquido,
    e.vl_empenhado_compartilhado::numeric(15, 2) as vl_empenhado_compartilhado,
    e.vl_pago_compartilhado::numeric(15, 2) as vl_pago_compartilhado,
    e.ds_instrumento_compartilhado::text as ds_instrumento_compartilhado,
    e.ds_origem_execucao::text as ds_origem_execucao
from execucao as e
left join credito as cr on cr.id_plano_acao = e.id_plano_acao
