{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, item 3.5 do formulário de convênios (origem e fonte dos
  recursos): o empenho de cada convênio de coleta_convenio, aberto por ano, PTRES, fonte,
  natureza de despesa e emenda.

  Fonte: os empenhos do siconv. valor_empenho já é o valor líquido da NE (a anulação de
  empenho vem negativa e a de pré-empenho, positiva), então soma direto, sem olhar o tipo
  da nota; test_coleta_convenio_fonte_tipo_nota derruba o build se aparecer um tipo
  novo. O siconv não traz programa, ação nem UO: vêm do relatório de execução do PPA
  (ppa_tesouro), pelo convênio que a NE cita, o ano e o PTRES. Ligar pela NE não serve,
  porque o mesmo número de NE se repete em outras UGs.

  A emenda é ligada por NE: em numero_transferencia cada NE tem uma emenda só, mas um
  convênio pode ter mais de uma. Quando a NE não está lá (reforço de empenho), vale a
  emenda que a própria NE descreve, com 8 dígitos e sem o ano; ela é resolvida para o
  código de 12 dígitos pelas outras NEs do convênio. O tipo da emenda sai do resultado
  primário: 6 individual, 7 bancada, 8 comissão. O reforço sai com RP 2 e herda o tipo
  das outras NEs da emenda; RP 2 sem emenda é programação própria do MIR.
#}
with
    empenho as (
        select
            e.nr_convenio,
            e.nr_empenho,
            e.ug_emitente,
            e.ptres,
            e.natureza_despesa,
            e.valor_empenho,
            nullif(trim(e.resultado_primario), '') as rp,
            left(e.nr_empenho, 4)::integer as aa_emissao,
            -- Desde 2019 o siconv grava a fonte com um zero a mais à esquerda.
            case
                when e.fonte_recurso ~ '^0[0-9]{10}$'
                then substr(e.fonte_recurso, 2)
                else e.fonte_recurso
            end as cd_fonte,
            case
                when split_part(e.descricao_emenda_siafi, '-', 1) ~ '^[0-9]{8}$'
                then split_part(e.descricao_emenda_siafi, '-', 1)
            end as cd_emenda_8,
            nullif(trim(split_part(e.descricao_emenda_siafi, '-', 2)), '')
            as no_autor_descricao
        from {{ ref("empenho") }} as e
        inner join {{ ref("coleta_convenio") }} as c on c.nr_convenio = e.nr_convenio
    ),

    -- O mesmo autor aparece com grafias diferentes (caixa, espaço no fim).
    emenda_ne as (
        select
            ne_ccor,
            autor_emendas_orcamento as cd_emenda,
            max(trim(autor)) as no_autor
        from {{ ref("numero_transferencia") }}
        where autor_emendas_orcamento ~ '^[0-9]{12}$'
        group by ne_ccor, autor_emendas_orcamento
    ),

    ligado as (
        select e.*, n.cd_emenda as cd_emenda_12, n.no_autor
        from empenho as e
        left join
            emenda_ne as n
            on n.ne_ccor
            = lpad(e.ug_emitente::text, 6, '0') || '00001' || e.nr_empenho
    ),

    -- Código de 12 dígitos das emendas do convênio, para resolver os de 8.
    emenda_convenio as (
        select distinct nr_convenio, cd_emenda_12, no_autor
        from ligado
        where cd_emenda_12 is not null
    ),

    resolvido as (
        select
            l.*,
            coalesce(
                l.cd_emenda_12,
                (
                    select min(c.cd_emenda_12)
                    from emenda_convenio as c
                    where
                        c.nr_convenio = l.nr_convenio
                        and right(c.cd_emenda_12, 8) = l.cd_emenda_8
                    having count(*) = 1
                ),
                l.cd_emenda_8
            ) as cd_emenda,
            coalesce(
                l.no_autor,
                (
                    select min(c.no_autor)
                    from emenda_convenio as c
                    where
                        c.nr_convenio = l.nr_convenio
                        and right(c.cd_emenda_12, 8) = l.cd_emenda_8
                    having count(*) = 1
                ),
                l.no_autor_descricao
            ) as no_autor_emenda
        from ligado as l
    ),

    -- Tipo de cada emenda pelas NEs dela com RP de emenda.
    tipo_emenda as (
        select cd_emenda, min(rp) as rp
        from resolvido
        where cd_emenda is not null and rp in ('6', '7', '8')
        group by cd_emenda
        having count(distinct rp) = 1
    ),

    classificado as (
        select
            r.*,
            case
                when r.rp is null
                then null
                when coalesce(t.rp, r.rp) = '6'
                then 'Emenda parlamentar individual'
                when coalesce(t.rp, r.rp) = '7'
                then 'Emenda parlamentar de bancada'
                when coalesce(t.rp, r.rp) = '8'
                then 'Emenda parlamentar de comissão'
                when r.rp = '2' and r.cd_emenda is null
                then 'Programação própria do MIR'
                else 'Outra'
            end as tp_origem
        from resolvido as r
        left join tipo_emenda as t on t.cd_emenda = r.cd_emenda
    ),

    -- Sem desempate de propósito: duas combinações de programa e ação para o mesmo
    -- convênio, ano e PTRES duplicam a linha, e a chave do contrato derruba o build.
    programa as (
        select distinct
            ne_info_complementar as nr_convenio,
            ne_ccor_ano_emissao as aa_emissao,
            ptres,
            programa_governo as cd_programa,
            programa_governo_descricao as no_programa,
            acao_governo as cd_acao,
            acao_governo_descricao as no_acao,
            plano_orcamentario_codigo_uo as cd_uo
        from {{ ref("ppa_tesouro") }}
        where ne_info_complementar in (select nr_convenio from empenho)
    ),

    nome_fonte as (
        select
            fonte_recursos_detalhada as cd_fonte,
            max(fonte_recursos_detalhada_descricao) as no_fonte
        from {{ ref("ppa_tesouro") }}
        group by fonte_recursos_detalhada
    ),

    nome_natureza as (
        select
            natureza_despesa as cd_natureza_despesa,
            max(natureza_despesa_descricao) as no_natureza_despesa
        from {{ ref("ppa_tesouro") }}
        group by natureza_despesa
    )

select
    c.nr_convenio::text as nr_convenio,
    c.aa_emissao::integer as aa_emissao,
    p.cd_programa::text as cd_programa,
    p.no_programa::text as no_programa,
    p.cd_acao::text as cd_acao,
    p.no_acao::text as no_acao,
    p.cd_uo::text as cd_uo,
    c.ptres::text as cd_ptres,
    c.cd_fonte::text as cd_fonte,
    max(f.no_fonte)::text as no_fonte,
    c.natureza_despesa::text as cd_natureza_despesa,
    max(n.no_natureza_despesa)::text as no_natureza_despesa,
    c.tp_origem::text as tp_origem,
    coalesce(c.cd_emenda, 'sem_emenda')::text as cd_emenda,
    max(c.no_autor_emenda)::text as no_autor_emenda,
    sum(c.valor_empenho)::numeric(15, 2) as vl_empenhado
from classificado as c
left join
    programa as p
    on p.nr_convenio = c.nr_convenio
    and p.aa_emissao = c.aa_emissao
    and p.ptres = c.ptres
left join nome_fonte as f on f.cd_fonte = c.cd_fonte
left join nome_natureza as n on n.cd_natureza_despesa = c.natureza_despesa
group by
    c.nr_convenio,
    c.aa_emissao,
    p.cd_programa,
    p.no_programa,
    p.cd_acao,
    p.no_acao,
    p.cd_uo,
    c.ptres,
    c.cd_fonte,
    c.natureza_despesa,
    c.tp_origem,
    c.cd_emenda
