{{ config(materialized="table") }}

{#
  Tedinhos (NC do MIR sem número de transferência) identificados na página de
  transferências voluntárias do MIR no gov.br: uma linha por instrumento de
  ted_credito_instrumento, com o processo, o parceiro e o objeto da página. Porta
  analises/ted_execucao/govbr_pagina.py (instrumentos_da_pagina).

  Entradas da página que viram tedinho:
    - 'descentralização': bloco "Descentralização de Crédito ... Processo: ..."
      (descentralizacoes_gov_br);
    - 'TED sem nº Transferegov': TED com número do MIR na página, sem número do
      Transferegov e sem plano de ação (ted_gov_br), cujo valor não é o líquido de
      nenhum TED do SIAFI (ex.: TED 01/2026 da ENAP).

  A página não traz a NC; o vínculo é pelo valor, sem ratear:
    1. órgãos do parceiro: pela sigla no fim do nome ("... - IFG") nos planos de ação;
       sem TED nos planos, pelas palavras distintivas do nome (todas presentes no
       nome do órgão ou de suas UGs na consulta oficial, ex.: "... de Pelotas");
    2. NCs candidatas: tedinho positivo do ano da página ou do seguinte, para esses
       órgãos (para qualquer órgão, se nenhum foi achado);
    3. 'valor exato': um único instrumento tem NC com o valor da página (NCs fundidas
       como cancela-e-relança contam como um instrumento só);
    4. 'par de NCs': nenhuma NC tem o valor sozinha, e um único par de NCs soma o
       valor (ex.: processo 21290.001553/2025-06, 2025NC000449 + 2026NC000044).
  Valor repetido em instrumentos diferentes fica sem vínculo.
#}
with
    ug_orgao as (
        select distinct
            ug_executora_codigo as ug,
            orgao_uge_codigo as orgao,
            orgao_uge_nome,
            ug_executora_nome
        from {{ ref("execucao_ted_ug") }}
    ),

    -- ------------------------------------------------------------------ entradas
    ted_sem_numero as (
        select t.pagina, t.ordem, t.numero_ted, t.processo, t.parceiro, t.valor, t.url
        from {{ ref("teds_gov_br") }} as t
        inner join {{ ref("ted_gov_br") }} as g using (pagina, ordem)
        where t.num_transf is null and g.id_plano_acao is null and t.valor is not null
    ),

    liquido_ted as (
        select num_transf, sum(valor) as v
        from {{ ref("ted_credito_instrumento") }}
        where origem = 'TED'
        group by num_transf
    ),

    entradas as (
        select
            'descentralização' as tipo_entrada,
            pagina,
            ordem,
            null::text as numero_ted,
            processo,
            parceiro,
            objeto,
            valor,
            url
        from {{ ref("descentralizacoes_gov_br") }}
        where valor is not null
        union all
        select
            'TED sem nº Transferegov',
            s.pagina,
            s.ordem,
            s.numero_ted,
            s.processo,
            s.parceiro,
            null,
            s.valor,
            s.url
        from ted_sem_numero as s
        where not exists (select 1 from liquido_ted as l where abs(l.v - s.valor) < 0.01)
    ),

    entradas_id as (
        select
            e.*,
            e.pagina || '-' || e.tipo_entrada || '-' || e.ordem as id_entrada,
            left(e.pagina, 4)::integer as ano_pagina,
            -- "Universidade Federal de Pelotas - UFP" -> sigla UFP, nome antes do " - "
            upper(
                trim(
                    case
                        when e.parceiro like '% - %'
                        then regexp_replace(e.parceiro, '^.* - ', '')
                        else e.parceiro
                    end
                )
            ) as sigla,
            regexp_replace(coalesce(e.parceiro, ''), ' - [^-]*$', '') as nome
        from entradas as e
    ),

    -- ------------------------------------------------------- órgãos do parceiro
    por_sigla as (
        select distinct upper(trim(p.sigla_unidade_descentralizada)) as sigla, u.orgao
        from {{ ref("ted_plano_acao_consolidado") }} as p
        inner join ug_orgao as u on u.ug = p.cd_ug_unidade_descentralizada::text
        where p.sigla_unidade_descentralizada is not null
    ),

    palavras_orgao as (
        select distinct orgao, w[1] as palavra
        from
            ug_orgao,
            lateral regexp_matches(
                upper(
                    translate(
                        orgao_uge_nome || ' ' || ug_executora_nome,
                        'áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
                        'aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC'
                    )
                ),
                '[A-Z]{5,}',
                'g'
            ) as w
    ),

    palavras_entrada as (
        select distinct e.id_entrada, w[1] as palavra
        from
            entradas_id as e,
            lateral regexp_matches(
                upper(
                    translate(
                        e.nome,
                        'áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
                        'aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC'
                    )
                ),
                '[A-Z]{5,}',
                'g'
            ) as w
        where
            w[1] not in (
                'INSTITUTO',
                'FEDERAL',
                'UNIVERSIDADE',
                'FUNDACAO',
                'EDUCACAO',
                'CIENCIA',
                'TECNOLOGIA',
                'NACIONAL',
                'ESCOLA',
                'ESTADO',
                'FEDERAIS',
                'CAMPUS',
                'REITORIA',
                'ADMINISTRACAO',
                'PUBLICA',
                'DESENVOLVIMENTO'
            )
    ),

    por_nome as (
        select pe.id_entrada, po.orgao
        from palavras_entrada as pe
        inner join palavras_orgao as po using (palavra)
        group by pe.id_entrada, po.orgao
        having
            count(*) = (
                select count(*)
                from palavras_entrada as x
                where x.id_entrada = pe.id_entrada
            )
    ),

    orgaos_entrada as (
        select e.id_entrada, s.orgao
        from entradas_id as e
        inner join por_sigla as s using (sigla)
        union
        select n.id_entrada, n.orgao
        from por_nome as n
        where
            not exists (
                select 1
                from entradas_id as e
                inner join por_sigla as s using (sigla)
                where e.id_entrada = n.id_entrada
            )
    ),

    -- ----------------------------------------------------------- NCs candidatas
    ncs as (
        select
            nc,
            min(instrumento) as instrumento,
            min(orgao_ug) as orgao,
            substring(nc from 12 for 4)::integer as ano_nc,
            sum(valor) as v
        from {{ ref("ted_credito_instrumento") }}
        where origem = 'tedinho'
        group by nc
        having sum(valor) > 0.005
    ),

    candidatas as (
        select e.id_entrada, e.valor, n.nc, n.instrumento, n.v
        from entradas_id as e
        inner join ncs as n on n.ano_nc in (e.ano_pagina, e.ano_pagina + 1)
        where
            n.orgao
            in (select o.orgao from orgaos_entrada as o where o.id_entrada = e.id_entrada)
            or not exists (
                select 1 from orgaos_entrada as o where o.id_entrada = e.id_entrada
            )
    ),

    exato as (
        select id_entrada, min(instrumento) as instrumento
        from candidatas
        where abs(v - valor) < 0.01
        group by id_entrada
        having count(distinct instrumento) = 1
    ),

    pares as (
        select a.id_entrada, a.instrumento as inst_a, b.instrumento as inst_b
        from candidatas as a
        inner join
            candidatas as b
            on b.id_entrada = a.id_entrada
            and a.nc < b.nc
            and abs(a.v + b.v - a.valor) < 0.01
        where
            not exists (
                select 1
                from candidatas as c
                where c.id_entrada = a.id_entrada and abs(c.v - c.valor) < 0.01
            )
    ),

    par_unico as (
        select id_entrada, min(inst_a) as inst_a, min(inst_b) as inst_b
        from pares
        group by id_entrada
        having count(*) = 1
    ),

    vinculo as (
        select id_entrada, instrumento, 'valor exato' as metodo
        from exato
        union all
        select id_entrada, inst_a, 'par de NCs'
        from par_unico
        union all
        select id_entrada, inst_b, 'par de NCs'
        from par_unico
        where inst_b <> inst_a
    )

select distinct
    on (v.instrumento)
    v.instrumento,
    'tedinho ' || case
        when e.tipo_entrada = 'descentralização'
        then 'Processo ' || coalesce(e.processo, '?')
        else 'TED ' || e.numero_ted || ' (sem nº Transferegov)'
    end
    || ' ('
    || coalesce(nullif(e.sigla, ''), e.parceiro, '?')
    || ')' as nome_instrumento,
    e.tipo_entrada,
    e.numero_ted,
    e.processo,
    e.parceiro,
    e.sigla as parceiro_sigla,
    e.objeto,
    e.valor as valor_pagina,
    v.metodo,
    e.pagina,
    e.url
from vinculo as v
inner join entradas_id as e using (id_entrada)
order by v.instrumento, e.pagina, e.ordem
