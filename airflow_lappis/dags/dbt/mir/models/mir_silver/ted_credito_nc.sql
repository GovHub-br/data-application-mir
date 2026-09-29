{{ config(materialized="table") }}

-- Credito descentralizado (NC) dos TEDs do MIR, uma linha por movimento. So
-- entram as NCs ligadas a um numero de transferencia (TED), achado em tres
-- etapas: o campo nc_transferencia; o numero do TED no texto da NC (como na
-- cascata das NEs); e, por fim, o numero de outras NCs do mesmo processo SEI,
-- quando o processo tem um unico TED. O plano vem pelo sq_instrumento.
-- A fonte de 2026 traz cada movimento duas vezes (ORIGEM e DESTINO, mesmo
-- valor): fica so a ORIGEM. As NCs anteriores a 2026 vem sem data: usam 1 de
-- janeiro do ano do numero da NC, marcadas com data_estimada.
with
    nc as (
        select
            t.*,
            upper(regexp_replace(coalesce(t.descricao, ''), '\s+', ' ', 'g')) as texto,
            (
                regexp_match(
                    upper(coalesce(t.descricao, '')), '\m(\d{5}\.\d{6}/\d{4}-\d{2})\M'
                )
            )[1] as processo
        from {{ ref("nc_tesouro_mir") }} as t
        where coalesce(t.dc, 'ORIGEM') = 'ORIGEM'
    ),

    direto as (
        select
            nc.*,
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
            end as num_transf_direto,
            case
                when nc_transferencia <> '-8' then 'campo' else 'texto'
            end as fonte_direta
        from nc
    ),

    -- Processos com um unico TED: as NCs do processo sem numero herdam esse TED
    por_processo as (
        select processo, min(num_transf_direto) as num_transf
        from direto
        where num_transf_direto is not null and processo is not null
        group by processo
        having count(distinct num_transf_direto) = 1
    ),

    ligado as (
        select
            d.*,
            coalesce(d.num_transf_direto, p.num_transf) as num_transf,
            case
                when d.num_transf_direto is not null
                then d.fonte_direta
                when p.num_transf is not null
                then 'processo'
            end as metodo_vinculo
        from direto as d
        left join
            por_processo as p on p.processo = d.processo and d.num_transf_direto is null
    ),

    planos as (
        select distinct on (id_plano_acao) id_plano_acao, sq_instrumento
        from {{ ref("planos_acao_ted") }}
        where sq_instrumento is not null
        order by id_plano_acao, dt_ingest desc
    )

select
    md5(
        concat_ws(
            '|',
            l.nc,
            l.ptres,
            l.nc_natureza_despesa,
            l.nc_fonte_recursos,
            l.nc_evento,
            l.nc_evento_descricao,
            l.nc_plano_interno,
            l.nc_item_detalhamento,
            l.ro,
            l.favorecido_doc,
            l.valor_celula
        )
    ) as id_movimento,
    l.nc,
    case
        when l.nc_evento_descricao ~* '^DEV'
        then 'Devolvido'
        when l.nc_evento_descricao ~* '^ANU'
        then 'Anulado'
        when l.nc_evento_descricao ~* '^DESC'
        then 'Recebido'
    end as tipo,
    l.nc_evento_descricao as evento,
    coalesce(
        l.emissao_dia, make_date(substring(l.nc from 12 for 4)::integer, 1, 1)
    ) as data_movimento,
    l.emissao_dia is null as data_estimada,
    l.num_transf,
    l.metodo_vinculo,
    pl.id_plano_acao,
    case
        when left(l.nc, 2) = '81' then l.favorecido_doc else left(l.nc, 6)
    end as ug_executora_codigo,
    l.ptres,
    l.nc_natureza_despesa as natureza_despesa,
    l.nc_fonte_recursos as fonte_recursos,
    l.processo,
    l.valor_celula as valor
from ligado as l
left join planos as pl on pl.sq_instrumento = l.num_transf
where l.num_transf is not null
