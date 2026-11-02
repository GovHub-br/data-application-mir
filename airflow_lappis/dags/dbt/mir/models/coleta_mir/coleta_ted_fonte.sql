{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, item 3.5 do formulário de TEDs (programa orçamentário e fonte
  de recursos): o crédito descentralizado para cada TED de coleta_ted, aberto por ano,
  programa, ação, PTRES, fonte e natureza de despesa.

  Fonte: as NCs do SIAFI (nc_unificado), ligadas ao TED pelo número da transferência que
  a própria NC traz. A NC já vem com programa e ação; a UO sai do PTRES no relatório de
  execução do PPA (ppa_tesouro). valor_celula é sempre positivo e o sentido está no
  evento: a anulação (por quem descentralizou) e a devolução (pelo parceiro) reduzem o
  crédito.

  Só há NC carregada a partir de 2023. O TED sem nenhuma NC, como os de 2022, usa as
  notas e os eventos da API de TED. As duas fontes não se misturam: quando a NC do TED
  chega ao SIAFI, as linhas da API saem. A API só traz PTRES, fonte e natureza. A ação
  vem do programa do TED e o programa orçamentário vem da ação nas NCs; sem um valor
  único em cada passo, o TED fica sem linha. A UO fica nula: a API não a traz, e em 2022
  o crédito era de outro ministério (o MIR só existe desde 2023).
#}
with
    nc as (
        select n.*, c.id_plano_acao
        from {{ ref("nc_unificado") }} as n
        join {{ ref("coleta_ted") }} as c on c.nr_transferencia = n.nc_transferencia
    ),

    -- Sem desempate de propósito: um PTRES com duas UOs duplica a linha, e a chave do
    -- contrato derruba o build antes da troca da tabela.
    uo_por_ptres as (
        select distinct ptres::text as ptres, plano_orcamentario_codigo_uo as cd_uo
        from {{ ref("ppa_tesouro") }}
        where plano_orcamentario_codigo_uo is not null
    ),

    -- Eventos da API do TED sem nenhuma NC acima. A nota pendente de envio ainda não é
    -- crédito e nem tem data. A API grava parte das fontes em minúsculas, e a NC não.
    api as (
        select
            e.*,
            upper(e.cd_fonte_recurso) as cd_fonte,
            n.id_plano_acao,
            extract(year from n.dt_emissao_nota) as emissao_ano,
            p.id_programa
        from {{ ref("notas_de_credito") }} as n
        join {{ ref("coleta_ted") }} as c on c.id_plano_acao = n.id_plano_acao
        join {{ ref("planos_acao_portal_ted") }} as p on p.id_plano_acao = n.id_plano_acao
        join {{ ref("eventos_nota_credito_ted") }} as e on e.id_nota = n.id_nota
        where
            n.tx_situacao_nota = 'ENVIADA'
            and not exists (select 1 from nc where nc.id_plano_acao = n.id_plano_acao)
    ),

    -- A nota da API não diz a ação: com mais de uma no programa, não há como atribuir.
    -- As ações também vêm com caixa misturada (21ar).
    acao_por_programa as (
        select id_programa, max(upper(cd_acao_orcamentaria)) as cd_acao
        from {{ ref("programas_acao_orcamentaria_ted") }}
        group by id_programa
        having count(distinct upper(cd_acao_orcamentaria)) = 1
    ),

    programa_por_acao as (
        select
            acao_governo as cd_acao,
            max(acao_governo_descricao) as no_acao,
            max(programa_governo) as cd_programa,
            max(programa_governo_descricao) as no_programa
        from {{ ref("nc_unificado") }}
        group by acao_governo
        having count(distinct programa_governo) = 1
    ),

    nome_fonte as (
        select nc_fonte_recursos as cd_fonte, max(nc_fonte_recursos_descricao) as no_fonte
        from {{ ref("nc_unificado") }}
        group by nc_fonte_recursos
    )

select
    nc.id_plano_acao::integer as id_plano_acao,
    nc.emissao_ano::integer as aa_emissao,
    nc.programa_governo::text as cd_programa,
    max(nc.programa_governo_descricao)::text as no_programa,
    nc.acao_governo::text as cd_acao,
    max(nc.acao_governo_descricao)::text as no_acao,
    u.cd_uo::text as cd_uo,
    nc.ptres::text as cd_ptres,
    nc.nc_fonte_recursos::text as cd_fonte,
    max(nc.nc_fonte_recursos_descricao)::text as no_fonte,
    nc.nc_natureza_despesa::text as cd_natureza_despesa,
    max(nc.nc_natureza_despesa_descricao)::text as no_natureza_despesa,
    sum(nc.valor_celula) filter (
        where nc.nc_evento_descricao = 'DESCENTRALIZACAO DE CREDITO'
    )::numeric(15, 2) as vl_descentralizado,
    sum(nc.valor_celula) filter (
        where nc.nc_evento_descricao = 'ANULACAO DE DESCENTRALIZACAO DE CREDITO'
    )::numeric(15, 2) as vl_anulado,
    sum(nc.valor_celula) filter (
        where nc.nc_evento_descricao = 'DEVOLUCAO DE DESCENTRALIZACAO DE CREDITO'
    )::numeric(15, 2) as vl_devolvido,
    -- Soma todos os eventos, não só os três acima: um evento novo entra aqui e em
    -- nenhuma das três colunas, e o check do contrato derruba o build.
    sum(
        case
            when nc.nc_evento_descricao = 'DESCENTRALIZACAO DE CREDITO'
            then nc.valor_celula
            else - nc.valor_celula
        end
    )::numeric(15, 2) as vl_liquido,
    'siafi'::text as ds_origem_credito
from nc
left join uo_por_ptres as u on u.ptres = nc.ptres
group by
    nc.id_plano_acao,
    nc.emissao_ano,
    nc.programa_governo,
    nc.acao_governo,
    u.cd_uo,
    nc.ptres,
    nc.nc_fonte_recursos,
    nc.nc_natureza_despesa

union all

select
    api.id_plano_acao::integer as id_plano_acao,
    api.emissao_ano::integer as aa_emissao,
    g.cd_programa::text as cd_programa,
    max(g.no_programa)::text as no_programa,
    g.cd_acao::text as cd_acao,
    max(g.no_acao)::text as no_acao,
    null::text as cd_uo,
    api.cd_ptres::text as cd_ptres,
    api.cd_fonte::text as cd_fonte,
    max(f.no_fonte)::text as no_fonte,
    api.cd_natureza_despesa::text as cd_natureza_despesa,
    max(api.ds_natureza_despesa)::text as no_natureza_despesa,
    sum(api.vl_evento) filter (where api.cd_evento = '300300')::numeric(
        15, 2
    ) as vl_descentralizado,
    sum(api.vl_evento) filter (where api.cd_evento = '300302')::numeric(
        15, 2
    ) as vl_anulado,
    sum(api.vl_evento) filter (where api.cd_evento = '300301')::numeric(
        15, 2
    ) as vl_devolvido,
    -- Mesma guarda da NC: um evento novo não fecha a conta e derruba o build.
    sum(
        case when api.cd_evento = '300300' then api.vl_evento else - api.vl_evento end
    )::numeric(15, 2) as vl_liquido,
    'api_ted'::text as ds_origem_credito
from api
join acao_por_programa as a on a.id_programa = api.id_programa
join programa_por_acao as g on g.cd_acao = a.cd_acao
left join nome_fonte as f on f.cd_fonte = api.cd_fonte
group by
    api.id_plano_acao,
    api.emissao_ano,
    g.cd_programa,
    g.cd_acao,
    api.cd_ptres,
    api.cd_fonte,
    api.cd_natureza_despesa
