{{ config(materialized="table") }}

{#
  Camadas 1 e 2 da execução dos TEDs por instrumento (analises/ted_execucao/pipeline.py,
  até o descarte por crédito): cada NE fica com a primeira regra que a resolve.

    1 cascata dbt   vínculo NE -> TED de empenhos_por_plano_acao (o num_transf mais
                    frequente da NE).
    2 regras        só para as NEs da consulta oficial que a cascata não ligou:
                    A1 número do TransfereGov no texto; A2 numeração do MIR ("TED 17/2026")
                    resolvida pela página do gov.br (ted_gov_br); D NC citada no texto
                    (nc_plano_acao); B NE de referência (reforço), C mesmo processo e
                    E mesmo contrato, que herdam o TED de outra NE do mesmo órgão.
  Em todas, o TED precisa ser do órgão da UG da NE e o candidato precisa ser único.

  B, C e E propagam até não mudar mais nada (uma NE ligada numa rodada pode ligar outra
  na seguinte). Aqui são rodadas fixas; o teste test_execucao_ted_ne_vinculo_convergiu
  garante que a última rodada não ligou nada.

  Depois, dois descartes (a NE volta sem instrumento para as regras de crédito):
    - número que não é TED do MIR: nem plano de ação (ted_plano_acao_consolidado) nem
      crédito com número de transferência (ted_credito_instrumento);
    - vínculo que contradiz o crédito: a célula (ano, órgão, PTRES, fonte) tem crédito que
      explica todo o destaque oficial, o TED da NE não está nele e a célula não recebeu
      tedinho (NC sem número, que pode ser do próprio TED citado no texto).

  Grão: uma linha por NE da consulta oficial (execucao_ted_ne.oficial).
#}
{% set rodadas = var("ted_execucao_rodadas", 8) %}

with
    orgao_da_ug as (
        select ug_executora_codigo as ug, min(orgao_uge_codigo) as orgao
        from {{ ref("execucao_ted_ug") }}
        group by ug_executora_codigo
    ),

    planos as (
        select sq_instrumento as num_transf, id_plano_acao, cd_ug_unidade_descentralizada as ug_rec
        from {{ ref("ted_plano_acao_consolidado") }}
        where sq_instrumento is not null
    ),

    credito_ted as (
        select distinct num_transf, ug
        from {{ ref("ted_credito_instrumento") }}
        where origem = 'TED'
    ),

    teds_mir as (
        select num_transf from planos
        union
        select num_transf from credito_ted
    ),

    orgao_do_ted as (
        select distinct p.num_transf, o.orgao
        from planos as p
        inner join orgao_da_ug as o on o.ug = p.ug_rec
        union
        select distinct c.num_transf, o.orgao
        from credito_ted as c
        inner join orgao_da_ug as o on o.ug = c.ug
    ),

    -- num_transf mais frequente da NE na cascata (empate: o menor)
    cascata as (
        select ne_ccor, num_transf
        from
            (
                select
                    ne_ccor,
                    num_transf,
                    row_number() over (
                        partition by ne_ccor order by count(*) desc, num_transf collate "C"
                    ) as rn
                from
                    (
                        select distinct ne_ccor, num_transf, plano_acao, metodo
                        from {{ ref("empenhos_por_plano_acao") }}
                        where num_transf is not null
                    ) as d
                group by ne_ccor, num_transf
            ) as x
        where rn = 1
    ),

    ne as (
        select b.*, c.num_transf as vinc
        from {{ ref("execucao_ted_ne") }} as b
        left join cascata as c on c.ne_ccor = b.ne_ccor
    ),

    alvo as (
        select ne_ccor, orgao_ug as org, texto
        from ne
        where oficial and tem_movimento and vinc is null
    ),

    -- ------------------------------------------------------------- A1, A2 e D
    a1 as (
        select a.ne_ccor, min(t.tok) as instrumento
        from alvo as a
        cross join lateral (
            select distinct m[1] as tok
            from regexp_matches(a.texto, '\y([0-9]{6}|[0-9][A-Z]{3}[A-Z0-9]{2})\y', 'g') as m
        ) as t
        inner join teds_mir as tm on tm.num_transf = t.tok
        inner join orgao_do_ted as ot on ot.num_transf = t.tok and ot.orgao = a.org
        group by a.ne_ccor
        having count(distinct t.tok) = 1
    ),

    numeracao_gov_br as (
        select distinct numero_ted, num_transf
        from {{ ref("ted_gov_br") }}
        where num_transf is not null
    ),

    a2 as (
        select a.ne_ccor, min(g.num_transf) as instrumento
        from alvo as a
        cross join lateral regexp_matches(
            a.texto,
            'TED\s*(?:MIR|SEPAR/MIR|SEPAR|N[º°O]?\.?)?\s*(?:N[º°O]\.?\s*)?([0-9]{1,2})\s*/\s*([0-9]{4}|[0-9]{2})\y',
            'g'
        ) as m
        inner join
            numeracao_gov_br as g
            on g.numero_ted = lpad((m[1]::integer)::text, 2, '0')
            || '/'
            || case when length(m[2]) = 4 then m[2] else '20' || m[2] end
        inner join orgao_do_ted as ot on ot.num_transf = g.num_transf and ot.orgao = a.org
        where a.ne_ccor not in (select ne_ccor from a1)
        group by a.ne_ccor
        having count(distinct g.num_transf) = 1
    ),

    nc_com_plano as (
        select n.nc, n.id_plano_acao, o1.orgao as orgao_fav, o2.orgao as orgao_emit
        from {{ ref("nc_plano_acao") }} as n
        left join orgao_da_ug as o1 on o1.ug = n.favorecido_doc
        left join orgao_da_ug as o2 on o2.ug = n.ug_emitente
        where n.id_plano_acao is not null
    ),

    d as (
        select a.ne_ccor, min(p.num_transf) as instrumento
        from alvo as a
        cross join lateral (
            select distinct m[1] as suf
            from regexp_matches(a.texto, '([0-9]{4}NC[0-9]{6})', 'g') as m
        ) as c
        inner join
            nc_com_plano as n
            on right(n.nc, 12) = c.suf
            and (n.orgao_fav = a.org or n.orgao_emit = a.org)
        inner join planos as p on p.id_plano_acao = n.id_plano_acao
        where
            a.ne_ccor not in (select ne_ccor from a1)
            and a.ne_ccor not in (select ne_ccor from a2)
        group by a.ne_ccor
        having count(distinct p.num_transf) = 1
    ),

    achado_0 as (
        select ne_ccor, instrumento, 'A1 nº TransfereGov no texto' as regra, null::integer as rodada
        from a1
        union all
        select ne_ccor, instrumento, 'A2 numeração MIR (gov.br)', null
        from a2
        union all
        select ne_ccor, instrumento, 'D NC citada no texto', null
        from d
    ),

    -- ------------------------------------------- vizinhança das regras de propagação
    -- B: NE que cita outra NE da mesma UG ("2024NE000123") e vice-versa
    viz_b as (
        select distinct x.ne_ccor as ne, o.ne_ccor as viz
        from ne as x
        cross join lateral (
            select distinct m[1] as ref
            from regexp_matches(x.texto, '([0-9]{4}NE[0-9]{6})', 'g') as m
        ) as r
        inner join
            ne as o
            on left(o.ne_ccor, 6) = left(x.ne_ccor, 6)
            and right(o.ne_ccor, 12) = r.ref
            and o.ne_ccor <> x.ne_ccor
    ),

    vizinhos_b as (
        select ne, viz from viz_b
        union
        select viz, ne from viz_b
    ),

    -- C: mesmo processo (do texto ou do campo da NE), no mesmo órgão
    chaves_c as (
        select distinct ne_ccor, orgao_ug as org, right(p, 17) as chave
        from
            (
                select
                    x.ne_ccor,
                    x.orgao_ug,
                    regexp_replace(m[1], '\D', '', 'g') as p
                from ne as x
                cross join lateral regexp_matches(
                    x.texto,
                    '([0-9]{5}[.\s]?[0-9]{6}[/.\s]?[0-9]{4}[-.\s]?[0-9]{2})',
                    'g'
                ) as m
                union all
                select ne_ccor, orgao_ug, processo
                from ne
                where processo is not null
            ) as c
        where length(p) >= 15
    ),

    -- E: mesmo contrato, no mesmo órgão
    chaves_e as (
        select distinct x.ne_ccor, x.orgao_ug as org, regexp_replace(m[1], '\s', '', 'g') as chave
        from ne as x
        cross join lateral regexp_matches(
            x.texto, 'CONTRATO\s+([A-Z./-]*\s*[0-9]{1,4}/[0-9]{4})', 'g'
        ) as m
    ),

    vizinhos_c as (
        select distinct a.ne_ccor as ne, b.ne_ccor as viz
        from chaves_c as a
        inner join chaves_c as b on b.org = a.org and b.chave = a.chave and b.ne_ccor <> a.ne_ccor
    ),

    vizinhos_e as (
        select distinct a.ne_ccor as ne, b.ne_ccor as viz
        from chaves_e as a
        inner join chaves_e as b on b.org = a.org and b.chave = a.chave and b.ne_ccor <> a.ne_ccor
    ),

    {% set passos = [
        ("b", "B NE de referência (reforço)"),
        ("c", "C mesmo processo"),
        ("e", "E mesmo contrato"),
    ] %}
    {% set ns = namespace(anterior="achado_0") %}
    {% for regra, rotulo in passos %}
    {% for r in range(rodadas) %}
    {% set atual = "achado_" ~ regra ~ "_" ~ r %}
    {{ atual }} as (
        select * from {{ ns.anterior }}
        union all
        select a.ne_ccor, min(td.instrumento), '{{ rotulo }}', {{ r }}
        from alvo as a
        inner join vizinhos_{{ regra }} as v on v.ne = a.ne_ccor
        inner join
            (
                select ne_ccor, vinc as instrumento from ne where vinc is not null
                union all
                select ne_ccor, instrumento from {{ ns.anterior }}
            ) as td
            on td.ne_ccor = v.viz
        inner join orgao_do_ted as ot on ot.num_transf = td.instrumento and ot.orgao = a.org
        where a.ne_ccor not in (select ne_ccor from {{ ns.anterior }})
        group by a.ne_ccor
        having count(distinct td.instrumento) = 1
    ),
    {% set ns.anterior = atual %}
    {% endfor %}
    {% endfor %}

    atribuido as (
        select
            n.*,
            case
                when n.vinc is not null then n.vinc else a.instrumento
            end as instrumento_bruto,
            case when n.vinc is not null then '1 cascata dbt' else a.regra end as regra_bruta,
            a.rodada
        from ne as n
        left join {{ ns.anterior }} as a on a.ne_ccor = n.ne_ccor
        where n.oficial
    ),

    -- número que não é TED do MIR: descarta
    sem_falso as (
        select
            a.*,
            case when t.num_transf is not null then a.instrumento_bruto end as instrumento,
            case when t.num_transf is not null then a.regra_bruta end as regra
        from atribuido as a
        left join teds_mir as t on t.num_transf = a.instrumento_bruto
    ),

    -- ----------------------------------------- vínculo que contradiz o crédito da célula
    credito_celula as (
        select celula_credito as grp, sum(valor) as total
        from {{ ref("ted_credito_instrumento") }}
        group by celula_credito
    ),

    credito_instrumento as (
        select celula_credito as grp, instrumento
        from {{ ref("ted_credito_instrumento") }}
        where instrumento <> '(devolução sem TED)'
        group by celula_credito, instrumento
        having sum(valor) > 0.005
    ),

    destaque as (
        select
            concat_ws('|', ano_lancamento, orgao_uge_codigo, ptres, fonte_recursos_detalhada) as grp,
            sum(destaque_recebido) as destaque
        from {{ ref("execucao_ted_ug") }}
        group by 1
    ),

    cobertas as (
        select c.grp
        from credito_celula as c
        left join destaque as d on d.grp = c.grp
        where abs(c.total - coalesce(d.destaque, 0)) < 0.01
    ),

    com_tedinho as (
        select distinct grp from credito_instrumento where instrumento like 'tedinho%'
    )

select
    s.ne_ccor,
    s.ano,
    s.ug,
    s.orgao_ug,
    s.acao,
    s.po,
    s.ptres,
    s.grupo,
    s.fonte,
    s.celula_credito,
    s.emp,
    s.liq,
    s.pag,
    s.tem_movimento,
    s.texto,
    s.instrumento_bruto,
    s.regra_bruta,
    case when contradiz then null else s.instrumento end as instrumento,
    case when contradiz then null else s.regra end as regra,
    s.rodada as rodada_propagacao
from
    (
        select
            sf.*,
            (
                sf.instrumento is not null
                and sf.celula_credito in (select grp from cobertas)
                and sf.celula_credito not in (select grp from com_tedinho)
                and not exists (
                    select 1
                    from credito_instrumento as ci
                    where ci.grp = sf.celula_credito and ci.instrumento = sf.instrumento
                )
            ) as contradiz
        from sem_falso as sf
    ) as s
