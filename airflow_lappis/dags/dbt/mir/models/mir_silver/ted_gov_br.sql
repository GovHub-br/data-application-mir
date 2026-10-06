{{ config(materialized="table") }}

-- TEDs das páginas de transferências voluntárias do gov.br ligados ao plano de
-- ação: a ponte entre o número/ano do TED ("05/2026", como as NEs citam) e o
-- número da transferência. A página tem erros de digitação, então o plano é
-- achado nesta ordem:
-- 1. 'numero da pagina': o número do título existe como sq_instrumento;
-- 2. 'numero alternativo': outro número citado no bloco existe (ex.: 05/2026,
-- título 996644, texto 996694);
-- 3. 'valor e ano': nenhum número existe, mas há um único plano do mesmo ano
-- com o mesmo valor que nenhum outro TED da página já pegou (ex.: 17/2024,
-- 963746 na página, plano 967346).
-- Sem plano, id_plano_acao fica nulo (TEDs que o Transferegov não tem, ou
-- empate de valor e ano).
with
    teds as (select * from {{ ref("teds_gov_br") }}),

    planos as (
        select id_plano_acao, sq_instrumento, aa_instrumento, vl_total_plano_acao
        from {{ ref("ted_plano_acao_consolidado") }}
        where sq_instrumento is not null
    ),

    candidatos as (
        select t.pagina, t.ordem, c.num_transf, c.posicao
        from teds as t
        cross join
            lateral unnest(
                array[t.num_transf]
                || coalesce(string_to_array(t.num_transf_alternativos, ';'), '{}')
            )
        with ordinality as c(num_transf, posicao)
        where c.num_transf is not null
    ),

    por_numero as (
        select distinct
            on (c.pagina, c.ordem)
            c.pagina,
            c.ordem,
            p.id_plano_acao,
            case
                when c.posicao = 1 then 'numero da pagina' else 'numero alternativo'
            end as metodo
        from candidatos as c
        inner join planos as p on p.sq_instrumento = c.num_transf
        order by c.pagina, c.ordem, c.posicao
    ),

    sem_numero as (
        select t.*
        from teds as t
        left join por_numero as n using (pagina, ordem)
        where n.pagina is null
    ),

    por_valor as (
        select s.pagina, s.ordem, min(p.id_plano_acao) as id_plano_acao
        from sem_numero as s
        inner join
            planos as p
            on p.aa_instrumento = s.ano_ted
            and p.vl_total_plano_acao = s.valor
        where p.id_plano_acao not in (select id_plano_acao from por_numero)
        group by s.pagina, s.ordem
        having count(*) = 1
    ),

    vinculo as (
        select pagina, ordem, id_plano_acao, metodo
        from por_numero
        union all
        select pagina, ordem, id_plano_acao, 'valor e ano'
        from por_valor
    )

select
    t.pagina || '-' || t.ordem as id_ted,
    t.pagina,
    t.ordem,
    t.numero_ted,
    t.ano_ted,
    v.id_plano_acao,
    p.sq_instrumento as num_transf,
    t.num_transf as num_transf_pagina,
    t.num_transf_alternativos,
    coalesce(v.metodo, 'sem plano') as metodo_vinculo,
    t.processo,
    t.parceiro,
    t.valor,
    p.vl_total_plano_acao as valor_plano,
    -- Valor diferente não invalida o vínculo (aditivos de valor mudam o plano),
    -- mas marca os casos a conferir (ex.: 13/2025, título com o número de outro TED).
    t.valor = p.vl_total_plano_acao as valor_confere,
    t.url,
    t.dt_ingest
from teds as t
left join vinculo as v using (pagina, ordem)
left join planos as p on p.id_plano_acao = v.id_plano_acao
