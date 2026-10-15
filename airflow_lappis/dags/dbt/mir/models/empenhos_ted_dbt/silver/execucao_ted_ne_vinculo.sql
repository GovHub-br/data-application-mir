{{ config(materialized="table") }}

{#
  Camadas 4 e 5 da execução dos TEDs por instrumento (analises/ted_execucao/pipeline.py):
  as NEs da consulta oficial que as camadas 1 e 2 (execucao_ted_ne_regras) não ligaram
  ganham instrumento pelo crédito (ted_credito_instrumento) da sua célula (ano, órgão,
  PTRES, fonte). Cada NE fica com a primeira regra que a resolve, nesta ordem:

    G1   todo o destaque oficial da célula veio de um único instrumento.
    G2   o empenho pendente da célula é exatamente o saldo de um dos instrumentos.
    G3   a célula não recebeu NC do MIR, e um instrumento do mesmo ano/PTRES/fonte foi para
         outro órgão, que repassou (crédito menos o que executou) exatamente o destaque
         dela (ex.: TED 949807, MIR -> MinC -> UNIFESP).
    G1b  a célula recebeu um único instrumento, que repassou parte pela G3; o que sobra é
         exatamente o destaque oficial (ex.: Palmares 2025, TED 966942).
    G4/G5 célula com 2+ instrumentos e crédito cobrindo o destaque: as NEs pendentes casam
         com o saldo de cada instrumento (macro ted_casar_saldos): valor exato, 2-3 NEs
         que somam um saldo, exclusão, ou fechamento conjunto ("A + B").
    T    NC do MIR citada no texto ("2025NC000307", "NC000307 / 233518", "(238012/000307/
         233518)"); se é tedinho cancelado e relançado, vai para a NC relançada.
    S    NC citada de outro órgão (subdescentralização) com um único TED do MIR no ano +
         PTRES (desempate pela fonte).
    R    NC citada de um intermediário: casamento com o saldo dos instrumentos dele.
    G3   (exclusão) célula sem NC do MIR: casamento com o saldo dos instrumentos do mesmo
         ano/PTRES/fonte em outros órgãos.
    G4/G5/G6 segunda passada do saldo na célula, agora aceitando o conjunto aberto.
    6    não identificado.
  Nada é rateado.

  Diferença de execução para o Python: lá as NEs de uma célula são casadas uma a uma; aqui
  cada rodada casa de uma vez as que não disputam instrumento. O teste
  test_execucao_ted_ne_vinculo_convergiu garante que as rodadas bastaram.

  Grão: uma linha por NE da consulta oficial.
#}
{% set rodadas = var("ted_execucao_rodadas", 8) %}

with
    orgao_da_ug as (
        select ug_executora_codigo as ug, min(orgao_uge_codigo) as orgao
        from {{ ref("execucao_ted_ug") }}
        group by ug_executora_codigo
    ),

    destaque as (
        select
            concat_ws('|', ano_lancamento, orgao_uge_codigo, ptres, fonte_recursos_detalhada) as grp,
            sum(destaque_recebido) as destaque
        from {{ ref("execucao_ted_ug") }}
        group by 1
    ),

    credito as (select * from {{ ref("ted_credito_instrumento") }}),

    -- crédito total da célula, inclusive devolução sem TED
    credito_celula as (
        select celula_credito as grp, sum(valor) as total from credito group by celula_credito
    ),

    -- crédito positivo de cada instrumento na célula
    cred as (
        select
            celula_credito as grp,
            ano,
            orgao_ug,
            ptres,
            fonte,
            instrumento,
            sum(valor) as valor
        from credito
        where instrumento <> '(devolução sem TED)'
        group by celula_credito, ano, orgao_ug, ptres, fonte, instrumento
        having sum(valor) > 0.005
    ),

    n_instrumentos as (select grp, count(*) as n from cred group by grp),

    celulas_do_instrumento as (
        select instrumento, count(*) as n from cred group by instrumento
    ),

    devolucao_sem_par as (
        select
            celula_credito as grp,
            nc,
            -sum(valor) as d,
            row_number() over (partition by celula_credito order by nc collate "C") as ordem
        from credito
        where instrumento = '(devolução sem TED)'
        group by celula_credito, nc
    ),

    planos as (
        select sq_instrumento as num_transf
        from {{ ref("ted_plano_acao_consolidado") }}
        where sq_instrumento is not null
    ),

    teds_mir as (
        select num_transf from planos
        union
        select num_transf from credito where origem = 'TED'
    ),

    s0 as (
        select
            ne_ccor,
            ano,
            orgao_ug,
            ptres,
            fonte,
            celula_credito as grp,
            emp,
            liq,
            pag,
            texto,
            instrumento,
            regra,
            null::text as modo,
            rodada_propagacao as rodada
        from {{ ref("execucao_ted_ne_regras") }}
    ),

    -- ----------------------------------------------------------------------- G1
    exclusivo as (
        select c.grp, min(c.instrumento) as instrumento
        from cred as c
        inner join credito_celula as cc on cc.grp = c.grp
        left join destaque as d on d.grp = c.grp
        group by c.grp, cc.total, d.destaque
        having count(*) = 1 and abs(cc.total - coalesce(d.destaque, 0)) < 0.01
    ),

    g1 as (
        select
            s.ne_ccor,
            e.instrumento,
            'G1 crédito exclusivo' as regra,
            null::text as modo,
            null::integer as rodada
        from s0 as s
        inner join exclusivo as e on e.grp = s.grp
        where s.instrumento is null
    ),

    s1 as ({{ ted_avanca_estado("s0", "g1") }}),

    -- ----------------------------------------------------------------------- G2
    ident_s1 as (
        select grp, instrumento, sum(emp) as e
        from s1
        where instrumento is not null
        group by grp, instrumento
    ),

    pendente_s1 as (
        select grp, sum(emp) as v
        from s1
        where instrumento is null
        group by grp
        having abs(sum(emp)) >= 0.005
    ),

    g2_celula as (
        select p.grp, min(c.instrumento) as instrumento
        from pendente_s1 as p
        inner join n_instrumentos as ni on ni.grp = p.grp and ni.n >= 2
        inner join cred as c on c.grp = p.grp
        left join ident_s1 as i on i.grp = c.grp and i.instrumento = c.instrumento
        where abs(c.valor - coalesce(i.e, 0) - p.v) < 0.01
        group by p.grp
        having count(*) = 1
    ),

    g2 as (
        select s.ne_ccor, g.instrumento, 'G2 saldo exato de um TED' as regra, null::text as modo, null::integer as rodada
        from s1 as s
        inner join g2_celula as g on g.grp = s.grp
        where s.instrumento is null
    ),

    s2 as ({{ ted_avanca_estado("s1", "g2") }}),

    -- ----------------------------------------------------------------------- G3
    repasse_disponivel as (
        select c.grp, c.ano, c.orgao_ug, c.ptres, c.fonte, c.instrumento, c.valor - coalesce(d.destaque, 0) as repassado
        from cred as c
        left join destaque as d on d.grp = c.grp
        where c.valor - coalesce(d.destaque, 0) > 0.005
    ),

    repasse as (
        select k.grp, min(r.instrumento) as instrumento, min(r.grp) as origem
        from (select distinct grp, ano, orgao_ug, ptres, fonte from s2) as k
        inner join destaque as d on d.grp = k.grp and abs(d.destaque) >= 0.005
        inner join
            repasse_disponivel as r
            on r.ano = k.ano
            and r.ptres = k.ptres
            and r.fonte = k.fonte
            and r.orgao_ug <> k.orgao_ug
            and abs(r.repassado - d.destaque) < 0.01
        where k.grp not in (select grp from cred)
        group by k.grp
        having count(*) = 1
    ),

    g3 as (
        select s.ne_ccor, r.instrumento, 'G3 repasse por outro órgão' as regra, null::text as modo, null::integer as rodada
        from s2 as s
        inner join repasse as r on r.grp = s.grp
        where s.instrumento is null
    ),

    s3 as ({{ ted_avanca_estado("s2", "g3") }}),

    -- ---------------------------------------------------------------------- G1b
    repassado as (
        select r.origem as grp, r.instrumento, sum(d.destaque) as rep
        from repasse as r
        inner join destaque as d on d.grp = r.grp
        where r.grp in (select distinct s.grp from s2 as s inner join g3 using (ne_ccor))
        group by r.origem, r.instrumento
    ),

    exclusivo_menos_repasse as (
        select c.grp, min(c.instrumento) as instrumento
        from cred as c
        inner join credito_celula as cc on cc.grp = c.grp
        left join destaque as d on d.grp = c.grp
        inner join repassado as rp on rp.grp = c.grp and rp.instrumento = c.instrumento
        where c.grp in (select grp from n_instrumentos where n = 1)
            and rp.rep > 0.005
            and abs(cc.total - rp.rep - coalesce(d.destaque, 0)) < 0.01
        group by c.grp
    ),

    g1b as (
        select s.ne_ccor, e.instrumento, 'G1b crédito exclusivo descontado o repasse' as regra, null::text as modo, null::integer as rodada
        from s3 as s
        inner join exclusivo_menos_repasse as e on e.grp = s.grp
        where s.instrumento is null
    ),

    s4 as ({{ ted_avanca_estado("s3", "g1b") }}),

    -- ------------------------------------------------- G4/G5 saldo na célula (1ª passada)
    {{ ted_saldo_celula("s4", "sc4", max_devolucoes=5) }},

    pend_cs1 as (
        select s.grp, s.ne_ccor, s.emp as v
        from s4 as s
        inner join n_instrumentos as ni on ni.grp = s.grp and ni.n >= 2
        inner join credito_celula as cc on cc.grp = s.grp
        left join destaque as d on d.grp = s.grp
        where s.instrumento is null
            and abs(s.emp) > 0.005
            and cc.total >= coalesce(d.destaque, 0) - 0.01
    ),

    saldo_cs1 as (select * from sc4_saldo where grp in (select grp from pend_cs1)),

    {{ ted_casar_saldos("pend_cs1", "saldo_cs1", "cs1", aberto=false, rodadas=rodadas) }},

    g45 as (
        select
            ne_ccor,
            instrumento,
            case modo
                when 'conjunto' then 'G5 fechamento conjunto na célula'
                when 'conjunto aberto' then 'G6 conjunto aberto na célula (sem fechamento exato)'
                when 'exclusão' then 'G4 saldo único na célula'
                else 'G5 saldo exato da NE na célula'
            end as regra,
            modo,
            rodada
        from cs1_resultado
    ),

    s5 as ({{ ted_avanca_estado("s4", "g45") }}),

    -- ----------------------------------------------------------- T e S (camada 5)
    -- NCs do MIR (sinal pelo valor até 2025, pelo tipo desde 2026), com o instrumento: o
    -- número de transferência ou, sem ele, o tedinho (a própria NC ou o par cancela-relança)
    nc_mir as (
        select
            t.nc,
            t.nc_transferencia,
            t.ptres,
            t.favorecido_doc as fav,
            substring(t.nc from 12 for 4) as ano_nc,
            right(t.nc, 6) as seq,
            o.orgao,
            t.movimento_liquido_moeda_origem as v,
            case
                when t.nc_transferencia <> '-8'
                then t.nc_transferencia
                else coalesce(ti.instrumento, 'tedinho ' || t.nc)
            end as instrumento
        from {{ ref("nc_tesouro_mir") }} as t
        left join orgao_da_ug as o on o.ug = t.favorecido_doc
        left join
            (select distinct nc, instrumento from credito where origem = 'tedinho') as ti
            on ti.nc = t.nc
        where
            left(t.nc, 6) in {{ ted_execucao_emitentes_mir() }}
            and t.relatorio = 'enviadas'
            and (
                (t.dc is null and (t.relatorio <> 'recebidas' or t.movimento_liquido_moeda_origem < 0))
                or (t.dc is not null and (t.relatorio <> 'recebidas' or t.nc_evento_descricao like 'DEVOLUCAO%'))
            )
    ),

    pend_t as (select * from s5 where instrumento is null),

    citacao_t1 as (
        select p.ne_ccor, m[1] as ano_cit, m[2] as seq
        from pend_t as p
        cross join lateral regexp_matches(p.texto, '([0-9]{4})NC([0-9]{6})', 'g') as m
        union
        select p.ne_ccor, p.ano::text, m[1]
        from pend_t as p
        cross join lateral regexp_matches(p.texto, '(?<![0-9])NC\s?([0-9]{6})\y', 'g') as m
    ),

    t1 as (
        select p.ne_ccor, min(n.instrumento) as instrumento, count(distinct n.instrumento) as n
        from pend_t as p
        inner join citacao_t1 as c on c.ne_ccor = p.ne_ccor
        inner join
            nc_mir as n
            on n.ano_nc = c.ano_cit
            and n.seq = c.seq
            and (n.orgao = p.orgao_ug or n.fav = left(p.ne_ccor, 6))
            and n.ptres = p.ptres
        where n.instrumento like 'tedinho%' or n.instrumento in (select num_transf from teds_mir)
        group by p.ne_ccor
    ),

    -- NC do MIR citada com a UG emitente, mesmo que tenha ido a um intermediário
    citacao_t2 as (
        select p.ne_ccor, m[1] as emit, m[2]::integer as seq, m[3] as ptres
        from pend_t as p
        cross join lateral regexp_matches(
            p.texto, '\y(238012|810008)[/-](?:NC)?0*([0-9]{1,6})[/-]([0-9]{6})\y', 'g'
        ) as m
        union
        select p.ne_ccor, m[3], m[2]::integer, m[1]
        from pend_t as p
        cross join lateral regexp_matches(
            p.texto, '\(([0-9]{6})/0*([0-9]{1,6})/(238012|810008)\)', 'g'
        ) as m
    ),

    t2 as (
        select p.ne_ccor, min(n.instrumento) as instrumento, count(distinct n.instrumento) as n
        from pend_t as p
        inner join citacao_t2 as c on c.ne_ccor = p.ne_ccor
        inner join
            nc_mir as n
            on left(n.nc, 6) = c.emit
            and n.seq::integer = c.seq
            and n.ptres = c.ptres
            and n.ano_nc = p.ano::text
            and n.ptres = p.ptres
        where
            (n.instrumento like 'tedinho%' or n.instrumento in (select num_transf from teds_mir))
            and p.ne_ccor not in (select ne_ccor from t1 where n = 1)
        group by p.ne_ccor
    ),

    t_bruto as (
        select ne_ccor, instrumento, '' as sufixo from t1 where n = 1
        union all
        select ne_ccor, instrumento, ' (via intermediário)' from t2 where n = 1
    ),

    -- tedinho cancelado e relançado: a NC citada não tem crédito líquido e o MIR mandou
    -- outra NC sem número ao mesmo órgão, no mesmo ano, com o mesmo valor bruto
    liquido_tedinho as (
        select orgao_ug, ano, instrumento, sum(valor) as liquido
        from credito
        where instrumento like 'tedinho%'
        group by orgao_ug, ano, instrumento
    ),

    bruto_tedinho as (
        select nc, orgao, ano_nc, sum(v) as v
        from nc_mir
        where nc_transferencia = '-8' and v > 0 and orgao is not null
        group by nc, orgao, ano_nc
    ),

    t_relancado as (
        select
            t.ne_ccor,
            case
                when t.instrumento not like 'tedinho%'
                then t.instrumento
                when coalesce(lq.liquido, 0) > 0.01
                then t.instrumento
                when b.nc is null
                then t.instrumento
                else
                    coalesce(
                        (
                            select min('tedinho ' || c.nc)
                            from bruto_tedinho as c
                            inner join
                                liquido_tedinho as lc
                                on lc.orgao_ug = p.orgao_ug
                                and lc.ano = p.ano
                                and lc.instrumento = 'tedinho ' || c.nc
                                and lc.liquido > 0.01
                            where
                                c.orgao = p.orgao_ug
                                and c.ano_nc = p.ano::text
                                and c.nc <> substring(t.instrumento from 9)
                                and abs(c.v - b.v) < 0.01
                            having count(*) = 1
                        ),
                        t.instrumento
                    )
            end as instrumento,
            case
                when t.instrumento like 'tedinho%' then 'T tedinho pela NC citada' else 'T NC do MIR citada (TED)'
            end || t.sufixo as regra
        from t_bruto as t
        inner join pend_t as p on p.ne_ccor = t.ne_ccor
        left join
            liquido_tedinho as lq
            on lq.orgao_ug = p.orgao_ug and lq.ano = p.ano and lq.instrumento = t.instrumento
        left join
            (select distinct on (nc) nc, v from bruto_tedinho order by nc, orgao, ano_nc) as b
            on b.nc = substring(t.instrumento from 9)
    ),

    -- S: primeira NC citada de outro órgão; único TED do MIR dele no ano + PTRES
    citacao_s as (
        select distinct on (p.ne_ccor) p.ne_ccor, m.g[1] as emit
        from pend_t as p
        cross join lateral regexp_matches(
            p.texto, '[0-9]{4}NC[0-9]{6}\s*\(([0-9]{6})/', 'g'
        ) with ordinality as m(g, ordem)
        inner join orgao_da_ug as o on o.ug = m.g[1]
        where o.orgao <> p.orgao_ug and p.ne_ccor not in (select ne_ccor from t_bruto)
        order by p.ne_ccor, m.ordem
    ),

    s_cand as (
        select
            c.ne_ccor,
            c.emit,
            count(distinct cr.num_transf) as n_todos,
            min(cr.num_transf) as um_todos,
            count(distinct cr.num_transf) filter (where cr.fonte = p.fonte) as n_fonte,
            min(cr.num_transf) filter (where cr.fonte = p.fonte) as um_fonte
        from citacao_s as c
        inner join pend_t as p on p.ne_ccor = c.ne_ccor
        inner join
            credito as cr
            on cr.origem = 'TED'
            and cr.ug = c.emit
            and cr.ano = p.ano
            and cr.ptres = p.ptres
        group by c.ne_ccor, c.emit
    ),

    s_sub as (
        select
            ne_ccor,
            case when n_todos = 1 then um_todos else um_fonte end as instrumento,
            'S subdescentralização via ' || emit as regra
        from s_cand
        where n_todos = 1 or (n_todos > 1 and n_fonte = 1)
    ),

    camada5 as (
        select ne_ccor, instrumento, regra, null::text as modo, null::integer as rodada
        from t_relancado
        union all
        select ne_ccor, instrumento, regra, null, null
        from s_sub
    ),

    s6 as ({{ ted_avanca_estado("s5", "camada5") }}),

    -- ---------------------------------------------------- R saldo do intermediário
    citacao_r as (
        select distinct on (p.ne_ccor)
            p.ne_ccor,
            concat_ws('|', p.ano, o.orgao, p.ptres, p.fonte) as grp_intermediario,
            m.g[2] || ':' || m.g[1] as nc_citada
        from s6 as p
        cross join lateral regexp_matches(
            p.texto, '([0-9]{4}NC[0-9]{6}(?:/[0-9]{3,6})?)\s*\(([0-9]{6})/', 'g'
        ) with ordinality as m(g, ordem)
        inner join orgao_da_ug as o on o.ug = m.g[2]
        where p.instrumento is null and o.orgao <> p.orgao_ug
        order by p.ne_ccor, m.ordem
    ),

    pend_r as (
        select c.grp_intermediario as grp, s.ne_ccor, s.emp as v
        from citacao_r as c
        inner join s6 as s on s.ne_ccor = c.ne_ccor
        where c.grp_intermediario in (select grp from cred)
    ),

    grupo_r as (
        select c.grp_intermediario as grp, c.ne_ccor, c.nc_citada as g
        from citacao_r as c
    ),

    {{ ted_saldo_celula("s6", "sc6", max_devolucoes=5) }},

    saldo_r as (select * from sc6_saldo where grp in (select grp from pend_r)),

    {{ ted_casar_saldos("pend_r", "saldo_r", "csr", grupo="grupo_r", aberto=true, rodadas=rodadas) }},

    r as (
        select
            ne_ccor,
            instrumento,
            case modo
                when 'conjunto' then 'R fechamento conjunto no intermediário'
                when 'conjunto aberto' then 'R conjunto aberto no intermediário (sem fechamento exato)'
                when 'grupo' then 'R saldo do intermediário por NC citada'
                when 'exclusão' then 'R saldo do intermediário por exclusão'
                else 'R saldo exato do intermediário'
            end as regra,
            modo,
            rodada
        from csr_resultado
    ),

    s7 as ({{ ted_avanca_estado("s6", "r") }}),

    -- ------------------------------------------------- G3 repasse por exclusão (G3b)
    {{ ted_saldo_celula("s7", "sc7", max_devolucoes=5) }},

    pend_g3b as (
        select s.grp, s.ne_ccor, s.emp as v
        from s7 as s
        where s.instrumento is null and abs(s.emp) > 0.005 and s.grp not in (select grp from cred)
    ),

    saldo_g3b as (
        select k.grp, sc.instrumento, sum(sc.s) as s
        from (select distinct grp, ano, orgao_ug, ptres, fonte from s7 where grp in (select grp from pend_g3b)) as k
        inner join
            (select distinct grp, ano, orgao_ug, ptres, fonte from cred) as kc
            on kc.ano = k.ano
            and kc.ptres = k.ptres
            and kc.fonte = k.fonte
            and kc.orgao_ug <> k.orgao_ug
        inner join sc7_saldo as sc on sc.grp = kc.grp
        group by k.grp, sc.instrumento
    ),

    {{ ted_casar_saldos("pend_g3b", "saldo_g3b", "csg", aberto=true, rodadas=rodadas) }},

    g3b as (
        select
            ne_ccor,
            instrumento,
            case
                when modo = 'conjunto aberto'
                then 'G6 conjunto aberto (repasse sem fechamento exato)'
                else 'G3 repasse por outro órgão (exclusão)'
            end as regra,
            modo,
            rodada
        from csg_resultado
    ),

    s8 as ({{ ted_avanca_estado("s7", "g3b") }}),

    -- ------------------------------------------------- G4/G5/G6 saldo na célula (2ª passada)
    {{ ted_saldo_celula("s8", "sc8", max_devolucoes=5) }},

    pend_cs2 as (
        select s.grp, s.ne_ccor, s.emp as v
        from s8 as s
        inner join n_instrumentos as ni on ni.grp = s.grp and ni.n >= 2
        inner join credito_celula as cc on cc.grp = s.grp
        left join destaque as d on d.grp = s.grp
        where s.instrumento is null
            and abs(s.emp) > 0.005
            and cc.total >= coalesce(d.destaque, 0) - 0.01
    ),

    saldo_cs2 as (select * from sc8_saldo where grp in (select grp from pend_cs2)),

    {{ ted_casar_saldos("pend_cs2", "saldo_cs2", "cs2", aberto=true, rodadas=rodadas) }},

    g456 as (
        select
            ne_ccor,
            instrumento,
            case modo
                when 'conjunto' then 'G5 fechamento conjunto na célula'
                when 'conjunto aberto' then 'G6 conjunto aberto na célula (sem fechamento exato)'
                when 'exclusão' then 'G4 saldo único na célula'
                else 'G5 saldo exato da NE na célula'
            end as regra,
            modo,
            rodada
        from cs2_resultado
    ),

    s9 as ({{ ted_avanca_estado("s8", "g456") }})

select
    s.ne_ccor,
    s.ano,
    left(s.ne_ccor, 6) as ug,
    s.orgao_ug,
    s.ptres,
    s.fonte,
    s.grp as celula_credito,
    s.emp,
    s.liq,
    s.pag,
    s.instrumento,
    case
        when s.instrumento is null then null
        when s.instrumento like 'tedinho%' then 'Tedinho'
        else 'TED'
    end as tipo_instrumento,
    coalesce(s.regra, '6 não identificado') as regra,
    case left(coalesce(s.regra, '6'), 1)
        when '1' then '1 cascata dbt'
        when 'A' then '2 regras determinísticas'
        when 'B' then '2 regras determinísticas'
        when 'C' then '2 regras determinísticas'
        when 'D' then '2 regras determinísticas'
        when 'E' then '2 regras determinísticas'
        when 'G' then '4 crédito da UG'
        when 'T' then '5 tedinho / subdescentralização'
        when 'S' then '5 tedinho / subdescentralização'
        when 'R' then '5 tedinho / subdescentralização'
        else '6 não identificado'
    end as grupo_regra,
    s.modo as modo_casamento,
    s.rodada
from s9 as s
