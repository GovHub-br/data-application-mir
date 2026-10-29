{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, item 3.5 do formulário de TEDs (programa orçamentário e fonte
  de recursos): o crédito que o MIR descentralizou para cada TED de coleta_ted, aberto
  por ano, programa, ação, PTRES, fonte e natureza de despesa.

  Fonte: as NCs do SIAFI (nc_unificado), ligadas ao TED pelo número da transferência que
  a própria NC traz. A NC já vem com programa e ação; a UO sai do PTRES no relatório de
  execução do PPA (ppa_tesouro). valor_celula é sempre positivo e o sentido está no
  evento: a anulação (pelo MIR) e a devolução (pelo parceiro) reduzem o crédito.

  Só há NC carregada a partir de 2023, então os TEDs de 2022 não aparecem aqui.
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
    )::numeric(15, 2) as vl_liquido
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
