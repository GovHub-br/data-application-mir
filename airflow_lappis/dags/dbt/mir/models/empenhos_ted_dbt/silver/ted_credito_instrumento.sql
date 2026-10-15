{{ config(materialized="table") }}

{#
  Crédito descentralizado pelo MIR por instrumento, uma linha por movimento de NC, com a
  célula de crédito (ano x órgão x PTRES x fonte) em que ele cai. Porta
  analises/ted_execucao/credito_total.py (credito()) a partir da bronze nc_tesouro_mir.

  Três origens:
    - 'TED': NC com número de transferência. O número vem do campo nc_transferencia, do
      texto da NC ("TED 949807", "EXECUCAO DESCENTRALIZADA ...") ou, sem nenhum dos dois, de
      outras NCs do mesmo processo SEI quando o processo tem um único TED. NCs internas do
      MIR (os dois lados no MIR) ficam fora. O valor tem o sinal do evento (anulação e
      devolução negativas). UG executora: o favorecido quando o MIR emite; o emitente
      quando o MIR recebe (devolução). "MIR" aqui é o seed ugs_mir, como no ted_credito_nc
      que o pipeline.py lê.
    - 'tedinho': NC do MIR sem número de transferência (nc_transferencia = '-8') para
      outro órgão. Instrumento = 'tedinho <NC>'. Nos tedinhos e nas devoluções o lado do MIR
      é o de credito_total.py (macro ted_execucao_lado_mir), que inclui os postos do MRE
      no exterior (240xxx).
    - 'devolução': devolução sem número de outro órgão para o MIR.
  Anulação (NC do MIR negativa) e devolução abatem a NC positiva que cancelam, nesta ordem
  (pipeline.py: casar_negativas): a NC citada na descrição do estorno ("ESTORNO DE NOTA DE
  CREDITO 2026NC000064"); senão a NC de itens idênticos (mesmos valores absolutos) da
  mesma UG e ano; senão a de mesmo valor total. Cada NC positiva é abatida uma vez só, na
  ordem das NCs negativas. Se o valor total empata com 2 ou 3 NCs, elas são um
  cancela-e-relança da mesma descentralização e viram um instrumento só ("NC_A / NC_B").
  A devolução que não abate nenhum tedinho fica como '(devolução sem TED)'.

  orgao_ug: órgão da UG na consulta oficial (execucao_ted_ug); UG fora dela (ex.: o MinC,
  que só repassou) fica como 'UG <código>', para não sumir nos agrupamentos.
#}
with
    orgao_da_ug as (
        select ug_executora_codigo as ug, min(orgao_uge_codigo) as orgao
        from {{ ref("execucao_ted_ug") }}
        group by ug_executora_codigo
    ),

    mir as (select ug_codigo from {{ ref("ugs_mir") }}),

    nc as (
        select
            t.*,
            left(t.nc, 6) as emit,
            substring(t.nc from 12 for 4)::integer as ano_nc,
            upper(regexp_replace(coalesce(t.descricao, ''), '\s+', ' ', 'g')) as texto
        from {{ ref("nc_tesouro_mir") }} as t
    ),

    -- ---------------------------------------------------------------- NC com nº de TED
    ted_direto as (
        select
            nc.*,
            (regexp_match(texto, '\m(\d{5}\.\d{6}/\d{4}-\d{2})\M'))[1] as processo,
            case
                when nc_transferencia <> '-8'
                then nc_transferencia
                else
                    (
                        regexp_match(
                            texto,
                            '(?:\mTED\M|EXECUCAO DESCENTRALIZADA)[^0-9]{0,12}?(?:\d{1,3}/\d{4} ?\( ?)?\m(\d{6}|\d[0-9A-Z]{5})\M'
                        )
                    )[1]
            end as num_transf_direto
        from nc
        where
            not (
                emit in (select ug_codigo from mir)
                and coalesce(favorecido_doc, '') in (select ug_codigo from mir)
            )
    ),

    por_processo as (
        select processo, min(num_transf_direto) as num_transf
        from ted_direto
        where num_transf_direto is not null and processo is not null
        group by processo
        having count(distinct num_transf_direto) = 1
    ),

    ted as (
        select
            d.nc,
            coalesce(d.num_transf_direto, p.num_transf) as num_transf,
            case
                when d.nc_evento_descricao ~* '^DEV' then 'Devolvido'
                when d.nc_evento_descricao ~* '^ANU' then 'Anulado'
                when d.nc_evento_descricao ~* '^DESC' then 'Recebido'
            end as tipo,
            extract(year from coalesce(d.emissao_dia, make_date(d.ano_nc, 1, 1)))::integer as ano,
            case
                when d.emit in (select ug_codigo from mir) then d.favorecido_doc else d.emit
            end as ug,
            d.ptres,
            d.nc_fonte_recursos as fonte,
            d.valor_celula
        from ted_direto as d
        left join
            por_processo as p
            on p.processo = d.processo and d.num_transf_direto is null
        where coalesce(d.num_transf_direto, p.num_transf) is not null
    ),

    -- ------------------------------------------------- NC sem nº (tedinho e devolução)
    -- Até 2025 o sinal vem no valor; desde 2026 vem do tipo da NC. Nas recebidas, só a
    -- devolução interessa (descentralização de outro órgão para o MIR sai).
    brutas as (
        select
            nc,
            emit,
            coalesce(favorecido_doc, '') as fav,
            ano_nc as ano,
            relatorio,
            ptres,
            nc_fonte_recursos as fonte,
            movimento_liquido_moeda_origem as v,
            case
                when ref[2] is not null
                then
                    coalesce(ref[1], substring(nc from 12 for 4))
                    || 'NC'
                    || lpad((ref[2]::bigint)::text, 6, '0')
            end as ref_estorno
        from
            (
                select
                    nc.*,
                    regexp_match(
                        coalesce(descricao, ''),
                        'ESTORNO D[AE] (?:NOTA DE CREDITO |NC\s?)?(?:([0-9]{4})NC)?0*([0-9]+)\y'
                    ) as ref
                from nc
                where
                    nc_transferencia = '-8'
                    and (
                        (dc is null and (relatorio <> 'recebidas' or movimento_liquido_moeda_origem < 0))
                        or (dc is not null and (relatorio <> 'recebidas' or nc_evento_descricao like 'DEVOLUCAO%'))
                    )
            ) as x
    ),

    tedinho as (
        select *
        from brutas
        where
            {{ ted_execucao_lado_mir("emit") }}
            and relatorio = 'enviadas'
            and not {{ ted_execucao_lado_mir("fav") }}
    ),

    devolucao as (
        select *
        from brutas
        where
            relatorio = 'recebidas'
            and {{ ted_execucao_lado_mir("fav") }}
            and not {{ ted_execucao_lado_mir("emit") }}
    ),

    -- uma linha por NC: UG do outro lado (executor), ano, total e os itens em valor absoluto
    itens as (
        select
            'tedinho' as origem,
            nc,
            min(fav) as ug,
            min(ano) as ano,
            sum(v) as total,
            array_agg(round(abs(v), 2) order by round(abs(v), 2)) as itens
        from tedinho
        group by nc
        union all
        select 'devolucao', nc, min(emit), min(ano), sum(v), array_agg(round(abs(v), 2) order by round(abs(v), 2))
        from devolucao
        group by nc
    ),

    positivas as (select * from itens where origem = 'tedinho' and total > 0.005),

    -- NCs negativas na ordem do Python: as do MIR (anulações) e depois as devoluções
    negativas as (
        select
            i.*,
            row_number() over (
                order by case when i.origem = 'tedinho' then 1 else 2 end, i.nc collate "C"
            ) as rn
        from itens as i
        where i.total < -0.005
    ),

    -- estorno que cita a NC estornada: a primeira negativa que cita uma positiva a leva
    estorno as (
        select distinct on (p.nc) n.nc as neg, p.nc as pos
        from negativas as n
        inner join
            (select nc, min(ref_estorno) as ref from (select nc, ref_estorno from tedinho union all select nc, ref_estorno from devolucao) as b where ref_estorno is not null group by nc) as c
            on c.nc = n.nc
        inner join positivas as p on right(p.nc, 12) = c.ref and left(p.nc, 6) = left(n.nc, 6)
        where
            (
                select count(*)
                from positivas as p2
                where right(p2.nc, 12) = c.ref and left(p2.nc, 6) = left(n.nc, 6)
            )
            = 1
        order by p.nc, n.rn
    ),

    -- duas passadas pelas negativas (itens idênticos, depois valor total), uma NC por passo
    passos as (
        select (pass - 1) * (select count(*) from negativas) + n.rn as passo, pass, n.*
        from negativas as n
        cross join (values (1), (2)) as v(pass)
    ),

    casamento as (
        with recursive
            r(passo, abatidas, casadas, mapa) as (
                select
                    0::bigint,
                    coalesce((select array_agg(pos) from estorno), array[]::text[]),
                    coalesce((select array_agg(neg) from estorno), array[]::text[]),
                    coalesce(
                        (
                            select jsonb_object_agg(k, rotulo)
                            from
                                (
                                    select neg as k, pos as rotulo from estorno
                                    union all
                                    select pos, pos from estorno
                                ) as e
                        ),
                        '{}'::jsonb
                    )
                union all
                select
                    r.passo + 1,
                    case when h.ok then r.abatidas || h.ncs else r.abatidas end,
                    case when h.ok then r.casadas || s.nc else r.casadas end,
                    case
                        when h.ok
                        then
                            r.mapa
                            || jsonb_build_object(s.nc, h.rotulo)
                            || (select jsonb_object_agg(x, h.rotulo) from unnest(h.ncs) as x)
                        else r.mapa
                    end
                from r
                inner join passos as s on s.passo = r.passo + 1
                left join lateral (
                    select
                        not (s.nc = any(r.casadas))
                        and (
                            count(*) = 1
                            or (s.pass = 2 and count(*) between 2 and 3)
                        ) as ok,
                        array_agg(p.nc order by p.nc collate "C") as ncs,
                        string_agg(p.nc, ' / ' order by p.nc collate "C") as rotulo
                    from positivas as p
                    where
                        p.ug = s.ug
                        and p.ano = s.ano
                        and not (p.nc = any(r.abatidas))
                        and (
                            (s.pass = 1 and p.itens = s.itens)
                            or (s.pass = 2 and abs(p.total + s.total) < 0.01)
                        )
                ) as h on true
            )
        select mapa from r order by passo desc limit 1
    ),

    rotulo_nc as (
        select m.key as nc, m.value as rotulo
        from casamento as c
        cross join lateral jsonb_each_text(c.mapa) as m
    ),

    movimentos as (
        select
            'TED' as origem,
            t.tipo,
            t.num_transf,
            t.nc,
            t.ano,
            t.ug,
            t.ptres,
            t.fonte,
            t.num_transf as instrumento,
            t.valor_celula
            * case t.tipo when 'Recebido' then 1 when 'Devolvido' then -1 when 'Anulado' then -1 end
            as valor
        from ted as t
        union all
        select
            'tedinho',
            null,
            null,
            td.nc,
            td.ano,
            td.fav,
            td.ptres,
            td.fonte,
            'tedinho ' || coalesce(rn.rotulo, td.nc),
            td.v
        from tedinho as td
        left join rotulo_nc as rn on rn.nc = td.nc
        union all
        select
            'devolucao',
            null,
            null,
            dv.nc,
            dv.ano,
            dv.emit,
            dv.ptres,
            dv.fonte,
            case
                when rn.rotulo is not null and rn.rotulo <> dv.nc
                then 'tedinho ' || rn.rotulo
                else '(devolução sem TED)'
            end,
            dv.v
        from devolucao as dv
        left join rotulo_nc as rn on rn.nc = dv.nc
    )

select
    m.origem,
    m.tipo,
    m.num_transf,
    m.nc,
    m.ano,
    m.ug,
    coalesce(o.orgao, 'UG ' || m.ug) as orgao_ug,
    m.ptres,
    m.fonte,
    concat_ws('|', m.ano, coalesce(o.orgao, 'UG ' || m.ug), m.ptres, m.fonte) as celula_credito,
    m.instrumento,
    m.valor
from movimentos as m
left join orgao_da_ug as o on o.ug = m.ug
