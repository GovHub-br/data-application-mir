{#
  Macros da execução dos TEDs por instrumento (execucao_ted_ne, ted_credito_instrumento,
  execucao_ted_ne_regras, execucao_ted_ne_vinculo). Portadas de analises/ted_execucao/
  (pipeline.py, credito_total.py), que continuam como referência das regras.

    ted_execucao_ugs_excluidas / ted_execucao_acoes_excluidas: recorte da consulta oficial
    "Execução TED por UG" (UGs e ações que ela não traz): as UGs do próprio MIR (810008,
    230003, 238012) e as de serviço compartilhado (CSC/MGI 170607, Diárias e Passagens
    170605, Central de Compras 201057, logística do MDHC 810005), e as ações
    administrativas. Dois consumidores: execucao_ted_ne (quais NEs entram) e tedinhos_mir
    (servico_administrativo: a NC para essas UGs ou ações não é tedinho). Mudar a lista
    muda também quantos tedinhos o painel mostra.
    ted_execucao_prefixos_lado_mir: prefixos do lado do MIR nas NCs sem número de
    transferência (credito_total.py: MIR): 238xxx, 810008, 230002 e os postos do MRE no
    exterior (240xxx), que executam despesa do próprio MIR (ex.: 240217, COP16 em Bogotá)
    e por isso não são parceiros. Só separa tedinho e devolução; não é a lista de UGs do
    MIR, que fica no seed ugs_mir e vale para as NCs de TED (ex.: a 240025, Agência
    Brasileira de Cooperação, recebe TED do MIR).
    ted_execucao_emitentes_mir: UGs do MIR que emitem as NCs citadas nas NEs.
    ted_execucao_lado_mir(col): a UG da coluna está no lado do MIR (prefixos acima).
#}

{% macro ted_execucao_ugs_excluidas() -%}
    ('810008', '170607', '170605', '201057', '230003', '810005', '238012')
{%- endmacro %}

{% macro ted_execucao_acoes_excluidas() -%}
    ('2000', '216H', '4641')
{%- endmacro %}

{% macro ted_execucao_prefixos_lado_mir() -%}
    {{ return(['238', '810008', '240', '230002']) }}
{%- endmacro %}

{% macro ted_execucao_emitentes_mir() -%}
    ('238012', '810008')
{%- endmacro %}

{% macro ted_execucao_lado_mir(col) -%}
    (
        {%- for p in ted_execucao_prefixos_lado_mir() %}
        {{ col }} like '{{ p }}%'{% if not loop.last %} or{% endif %}
        {%- endfor %}
    )
{%- endmacro %}

{#
  Células (ano x UG x ação x PO x PTRES x grupo x fonte) em que as NEs de execucao_ted_ne
  não reproduzem o empenhado, liquidado e pago da consulta oficial "Execução TED por UG".
  Base dos dois testes de reconciliação, que separam os exercícios pelo último ano da
  consulta oficial (o corrente):
    exercicios='fechados': os anos anteriores. Os dois relatórios são definitivos e têm de
      bater ao centavo (test_execucao_ted_ne_reconcilia_oficial_exercicios_fechados).
    exercicios='corrente': o último ano e os seguintes. As duas extrações podem ser de
      dias diferentes (test_execucao_ted_ne_reconcilia_oficial).
#}
{% macro ted_execucao_divergencia_oficial(exercicios) %}
    {% if exercicios not in ["fechados", "corrente"] %}
        {{ exceptions.raise_compiler_error("exercicios deve ser 'fechados' ou 'corrente'") }}
    {% endif %}
with
    oficial as (
        select
            ano_lancamento as ano,
            ug_executora_codigo as ug,
            acao_governo_codigo as acao,
            plano_orcamentario_codigo as po,
            ptres,
            grupo_despesa as grupo,
            fonte_recursos_detalhada as fonte,
            despesas_empenhadas as emp,
            despesas_liquidadas as liq,
            despesas_pagas as pag
        from {{ ref("execucao_ted_ug") }}
    ),

    corrente as (select max(ano) as ano from oficial),

    ne as (
        select ano, ug, acao, po, ptres, grupo, fonte, sum(emp) as emp, sum(liq) as liq, sum(pag) as pag
        from {{ ref("execucao_ted_ne") }}
        where ug in (select ug from oficial)
        group by ano, ug, acao, po, ptres, grupo, fonte
    )

select
    coalesce(o.ano, n.ano) as ano,
    coalesce(o.ug, n.ug) as ug,
    coalesce(o.acao, n.acao) as acao,
    coalesce(o.po, n.po) as po,
    coalesce(o.ptres, n.ptres) as ptres,
    coalesce(o.grupo, n.grupo) as grupo,
    coalesce(o.fonte, n.fonte) as fonte,
    o.emp as emp_oficial,
    n.emp as emp_ne,
    o.liq as liq_oficial,
    n.liq as liq_ne,
    o.pag as pag_oficial,
    n.pag as pag_ne
from oficial as o
full join ne as n using (ano, ug, acao, po, ptres, grupo, fonte)
where
    (
        abs(coalesce(o.emp, 0) - coalesce(n.emp, 0)) >= 0.01
        or abs(coalesce(o.liq, 0) - coalesce(n.liq, 0)) >= 0.01
        or abs(coalesce(o.pag, 0) - coalesce(n.pag, 0)) >= 0.01
    )
    and coalesce(o.ano, n.ano) {{ "<" if exercicios == "fechados" else ">=" }} (select ano from corrente)
{% endmacro %}

{#
  Saldo de cada instrumento numa célula (ano, órgão, PTRES, fonte), dado o estado atual da
  atribuição NE -> instrumento (pipeline.py: saldo_da_celula):
    saldo = crédito do instrumento na célula
            - o que as NEs da célula atribuídas a ele empenharam
            - o que NEs de OUTRAS células do mesmo ano, onde ele não tem crédito, empenharam
              com ele, quando ele só tem crédito nesta célula (repasse a outro órgão) ou
              quando a outra célula é do mesmo órgão e PTRES (o órgão remaneja a fonte).
  Depois, cada devolução sem par da célula (em ordem de NC) que é exatamente o saldo de um
  único instrumento o zera.

  estado: relação (grp, ano, orgao_ug, ptres, emp, instrumento) das NEs da consulta oficial.
  Gera CTEs; a última é {{ p }}_saldo (grp, instrumento, s).
#}
{% macro ted_saldo_celula(estado, p, max_devolucoes=3) %}
    {{ p }}_ident as (
        select grp, instrumento, sum(emp) as e
        from {{ estado }}
        where instrumento is not null
        group by grp, instrumento
    ),
    {{ p }}_fora as (
        select k.grp, k.instrumento, sum(st.emp) as e
        from cred as k
        inner join {{ estado }} as st on st.ano = k.ano and st.instrumento = k.instrumento
        inner join celulas_do_instrumento as cdi on cdi.instrumento = k.instrumento
        left join cred as c2 on c2.grp = st.grp and c2.instrumento = st.instrumento
        where
            c2.grp is null
            and (cdi.n = 1 or (st.orgao_ug = k.orgao_ug and st.ptres = k.ptres))
        group by k.grp, k.instrumento
    ),
    {{ p }}_saldo_0 as (
        select
            k.grp,
            k.instrumento,
            k.valor - coalesce(i.e, 0) - coalesce(f.e, 0) as s
        from cred as k
        left join {{ p }}_ident as i on i.grp = k.grp and i.instrumento = k.instrumento
        left join {{ p }}_fora as f on f.grp = k.grp and f.instrumento = k.instrumento
    ),
    {% for d in range(1, max_devolucoes + 1) %}
    {{ p }}_dev_{{ d }} as (
        select s.grp, min(s.instrumento) as instrumento, min(dv.d) as d
        from {{ p }}_saldo_{{ d - 1 }} as s
        inner join devolucao_sem_par as dv
            on dv.grp = s.grp and dv.ordem = {{ d }} and abs(s.s - dv.d) < 0.01
        group by s.grp
        having count(*) = 1
    ),
    {{ p }}_saldo_{{ d }} as (
        select
            s.grp,
            s.instrumento,
            s.s - coalesce(dv.d, 0) as s
        from {{ p }}_saldo_{{ d - 1 }} as s
        left join {{ p }}_dev_{{ d }} as dv
            on dv.grp = s.grp and dv.instrumento = s.instrumento
    ),
    {% endfor %}
    {{ p }}_saldo as (select * from {{ p }}_saldo_{{ max_devolucoes }})
{% endmacro %}

{#
  Casamento das NEs pendentes com o saldo dos instrumentos, sem ratear (pipeline.py:
  casar_saldos), em rodadas fixas. Em cada rodada e em cada grupo de casamento (grp):
    1. exato: NE cujo valor é o saldo de um único instrumento (se duas NEs disputam o
       mesmo instrumento, fica a de menor ne_ccor e a outra volta na rodada seguinte);
    2. grupo (só se `grupo` for informado e o passo 1 não casou nada no grp): NEs com a
       mesma NC citada cuja soma é o saldo de um único instrumento;
    3. subconjunto (só se 1 e 2 não casaram nada): 2 ou 3 NEs cuja soma é o saldo de um
       instrumento, quando é a única combinação que casa (grp com 3 a 12 NEs pendentes).
  Depois das rodadas, o que sobra vai para o único instrumento com saldo que o cobre
  (exclusão) ou, se 2 ou 3 instrumentos têm saldo, para a junção deles ("A + B") quando o
  saldo somado é exatamente o pendente (conjunto) ou, com `aberto`, quando o cobre
  (conjunto aberto).

  pend: relação (grp, ne_ccor, v); saldo: relação (grp, instrumento, s);
  grupo: relação (grp, ne_ccor, g) ou none.
  Gera CTEs; a última é {{ p }}_resultado (grp, ne_ccor, instrumento, modo, rodada).
  O Python processa as NEs uma a uma; aqui cada rodada casa todas as NEs que não disputam
  instrumento, e o teste test_execucao_ted_ne_vinculo_convergiu garante que a última
  rodada não casou nada (as rodadas bastaram).
#}
{% macro ted_casar_saldos(pend, saldo, p, grupo=none, aberto=false, rodadas=10) %}
    {{ p }}_pend_0 as (select grp, ne_ccor, v from {{ pend }}),
    {{ p }}_saldo_0 as (select grp, instrumento, s from {{ saldo }}),
    {% for r in range(rodadas) %}
    {{ p }}_exato_{{ r }} as (
        select distinct on (grp, instrumento) grp, ne_ccor, v, instrumento
        from
            (
                select
                    pe.grp,
                    pe.ne_ccor,
                    pe.v,
                    sa.instrumento,
                    count(*) over (partition by pe.grp, pe.ne_ccor) as n
                from {{ p }}_pend_{{ r }} as pe
                inner join
                    {{ p }}_saldo_{{ r }} as sa
                    on sa.grp = pe.grp and abs(sa.s - pe.v) < 0.01
            ) as h
        where n = 1
        order by grp, instrumento, ne_ccor
    ),
    {% if grupo is not none %}
    {{ p }}_grupo_{{ r }} as (
        select gm.grp, gm.ne_ccor, gm.v, gh.instrumento
        from
            (
                select distinct on (grp, instrumento) grp, g, instrumento
                from
                    (
                        select
                            gs.grp,
                            gs.g,
                            gs.primeiro,
                            sa.instrumento,
                            count(*) over (partition by gs.grp, gs.g) as n
                        from
                            (
                                select pe.grp, gr.g, sum(pe.v) as soma, min(pe.ne_ccor) as primeiro
                                from {{ p }}_pend_{{ r }} as pe
                                inner join
                                    {{ grupo }} as gr
                                    on gr.grp = pe.grp and gr.ne_ccor = pe.ne_ccor
                                where pe.grp not in (select grp from {{ p }}_exato_{{ r }})
                                group by pe.grp, gr.g
                                having count(*) > 1
                            ) as gs
                        inner join
                            {{ p }}_saldo_{{ r }} as sa
                            on sa.grp = gs.grp and abs(sa.s - gs.soma) < 0.01
                    ) as h
                where n = 1
                order by grp, instrumento, primeiro
            ) as gh
        inner join
            (
                select pe.grp, pe.ne_ccor, pe.v, gr.g
                from {{ p }}_pend_{{ r }} as pe
                inner join
                    {{ grupo }} as gr on gr.grp = pe.grp and gr.ne_ccor = pe.ne_ccor
            ) as gm
            on gm.grp = gh.grp and gm.g = gh.g
    ),
    {% endif %}
    {{ p }}_subbase_{{ r }} as (
        select pe.*, count(*) over (partition by pe.grp) as n
        from {{ p }}_pend_{{ r }} as pe
        where
            pe.grp not in (select grp from {{ p }}_exato_{{ r }})
            {% if grupo is not none %}
            and pe.grp not in (select grp from {{ p }}_grupo_{{ r }})
            {% endif %}
    ),
    {{ p }}_subcasa_{{ r }} as (
        select c.grp, c.nes, sa.instrumento
        from
            (
                select a.grp, array[a.ne_ccor, b.ne_ccor] as nes, a.v + b.v as soma
                from {{ p }}_subbase_{{ r }} as a
                inner join
                    {{ p }}_subbase_{{ r }} as b
                    on b.grp = a.grp and b.ne_ccor > a.ne_ccor
                where a.n between 3 and 12
                union all
                select a.grp, array[a.ne_ccor, b.ne_ccor, c.ne_ccor], a.v + b.v + c.v
                from {{ p }}_subbase_{{ r }} as a
                inner join
                    {{ p }}_subbase_{{ r }} as b
                    on b.grp = a.grp and b.ne_ccor > a.ne_ccor
                inner join
                    {{ p }}_subbase_{{ r }} as c
                    on c.grp = a.grp and c.ne_ccor > b.ne_ccor
                where a.n between 3 and 12
            ) as c
        inner join
            {{ p }}_saldo_{{ r }} as sa
            on sa.grp = c.grp and sa.s > 0.01 and abs(c.soma - sa.s) < 0.01
    ),
    {{ p }}_atrib_{{ r }} as (
        select grp, ne_ccor, v, instrumento, 'exato' as modo
        from {{ p }}_exato_{{ r }}
        {% if grupo is not none %}
        union all
        select grp, ne_ccor, v, instrumento, 'grupo'
        from {{ p }}_grupo_{{ r }}
        {% endif %}
        union all
        select sc.grp, pe.ne_ccor, pe.v, sc.instrumento, 'subconjunto'
        from {{ p }}_subcasa_{{ r }} as sc
        cross join lateral unnest(sc.nes) as u(ne_ccor)
        inner join {{ p }}_pend_{{ r }} as pe on pe.grp = sc.grp and pe.ne_ccor = u.ne_ccor
        where sc.grp in (select grp from {{ p }}_subcasa_{{ r }} group by grp having count(*) = 1)
    ),
    {{ p }}_pend_{{ r + 1 }} as (
        select pe.*
        from {{ p }}_pend_{{ r }} as pe
        where
            not exists (
                select 1
                from {{ p }}_atrib_{{ r }} as a
                where a.grp = pe.grp and a.ne_ccor = pe.ne_ccor
            )
    ),
    {{ p }}_saldo_{{ r + 1 }} as (
        select sa.grp, sa.instrumento, sa.s - coalesce(a.consumo, 0) as s
        from {{ p }}_saldo_{{ r }} as sa
        left join
            (
                select grp, instrumento, sum(v) as consumo
                from {{ p }}_atrib_{{ r }}
                group by grp, instrumento
            ) as a
            on a.grp = sa.grp and a.instrumento = sa.instrumento
    ),
    {% endfor %}
    {{ p }}_fim as (
        select
            pe.grp,
            sum(pe.v) as resto,
            max(cs.n) as n_com_saldo,
            max(cs.soma) as soma_saldo,
            max(cs.mesclado) as mesclado
        from {{ p }}_pend_{{ rodadas }} as pe
        inner join
            (
                select
                    grp,
                    count(*) as n,
                    sum(s) as soma,
                    string_agg(instrumento, ' + ' order by instrumento collate "C") as mesclado
                from {{ p }}_saldo_{{ rodadas }}
                where s > 0.01
                group by grp
            ) as cs
            on cs.grp = pe.grp
        group by pe.grp
    ),
    {{ p }}_resultado as (
        {% for r in range(rodadas) %}
        select grp, ne_ccor, instrumento, modo, {{ r }} as rodada from {{ p }}_atrib_{{ r }}
        union all
        {% endfor %}
        select
            pe.grp,
            pe.ne_ccor,
            fi.mesclado as instrumento,
            case
                when fi.n_com_saldo = 1 and fi.soma_saldo >= fi.resto - 0.01
                then 'exclusão'
                when fi.n_com_saldo between 2 and 3 and abs(fi.soma_saldo - fi.resto) < 0.01
                then 'conjunto'
                {% if aberto %}
                when fi.n_com_saldo between 2 and 3 and fi.soma_saldo >= fi.resto - 0.01
                then 'conjunto aberto'
                {% endif %}
            end as modo,
            {{ rodadas }} as rodada
        from {{ p }}_pend_{{ rodadas }} as pe
        inner join {{ p }}_fim as fi on fi.grp = pe.grp
        where
            (fi.n_com_saldo = 1 and fi.soma_saldo >= fi.resto - 0.01)
            or (fi.n_com_saldo between 2 and 3 and abs(fi.soma_saldo - fi.resto) < 0.01)
            {% if aberto %}
            or (fi.n_com_saldo between 2 and 3 and fi.soma_saldo >= fi.resto - 0.01)
            {% endif %}
    )
{% endmacro %}

{#
  Um passo da cascata de execucao_ted_ne_vinculo: a NE ainda sem instrumento em
  `anterior` fica com o da relação `novos` (ne_ccor, instrumento, regra, modo, rodada);
  a que já tinha instrumento não muda.
#}
{% macro ted_avanca_estado(anterior, novos) %}
    select
        s.ne_ccor,
        s.ano,
        s.orgao_ug,
        s.ptres,
        s.fonte,
        s.grp,
        s.emp,
        s.liq,
        s.pag,
        s.texto,
        coalesce(s.instrumento, n.instrumento) as instrumento,
        case when s.instrumento is null then n.regra else s.regra end as regra,
        case when s.instrumento is null then n.modo else s.modo end as modo,
        case when s.instrumento is null then n.rodada else s.rodada end as rodada
    from {{ anterior }} as s
    left join {{ novos }} as n on n.ne_ccor = s.ne_ccor
{% endmacro %}
