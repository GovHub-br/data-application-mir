{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR para os tedinhos: as descentralizações de crédito do MIR que não
  chegam a ser registradas no TransfereGov, uma linha por processo administrativo.

  A espinha é o seed tedinhos_identificados_mir, o levantamento manual na transparência
  ativa do gov.br: ele é superconjunto do que o SIAFI resolve (23 processos contra 19 em
  ted_tedinho_gov_br, e nenhum processo só no SIAFI), e o processo é o único identificador
  estável publicado. Por isso a chave é o processo, e não o instrumento: o instrumento sai
  de casamento por valor e muda quando chega NC nova.

  Fica fora de coleta_ted porque tedinho não tem id_plano_acao, cd_ted nem
  nr_transferencia, as três colunas not_null daquele contrato (ver coleta_tedinho.yml).

  O join com o SIAFI é pelos dígitos do processo: o seed grava com máscara
  (21290.002680/2025-14) e as duas pontas podem divergir na pontuação. Agrega por processo
  porque um processo pode ter duas NCs ('par de NCs'), e sem isso a linha se duplicaria e
  a chave do contrato derrubaria o build.
#}
with
    tedinho as (
        select
            processo,
            regexp_replace(processo, '\D', '', 'g') as processo_digitos,
            ano_publicacao,
            orgao_parceiro,
            numero_instrumento,
            objeto_resumo,
            valor_total,
            observacao,
            fonte_url
        from {{ ref("tedinhos_identificados_mir") }}
    ),

    pagina as (
        select regexp_replace(processo, '\D', '', 'g') as processo_digitos, instrumento
        from {{ ref("ted_tedinho_gov_br") }}
        where processo is not null
    ),

    siafi as (
        select
            processo_digitos,
            string_agg(
                distinct instrumento, '; ' order by instrumento
            ) as ds_instrumento_siafi
        from pagina
        group by processo_digitos
    ),

    execucao as (
        select
            p.processo_digitos,
            sum(g.empenhado) as vl_empenhado,
            sum(g.pago_total) as vl_pago
        from pagina as p
        join
            {{ ref("ted_execucao_por_instrumento") }} as g
            on g.instrumento = p.instrumento
        where g.tipo_instrumento <> 'TED'
        group by p.processo_digitos
    )

select
    t.processo::text as nr_processo_sei,
    t.ano_publicacao::integer as aa_publicacao,
    t.orgao_parceiro::text as sg_parceiro,
    t.numero_instrumento::text as nr_instrumento,
    t.objeto_resumo::text as ds_objeto,
    t.valor_total::numeric(15, 2) as vl_total,
    s.ds_instrumento_siafi::text as ds_instrumento_siafi,
    e.vl_empenhado::numeric(15, 2) as vl_empenhado,
    e.vl_pago::numeric(15, 2) as vl_pago,
    t.observacao::text as ds_observacao,
    t.fonte_url::text as ds_fonte_url
from tedinho as t
left join siafi as s on s.processo_digitos = t.processo_digitos
left join execucao as e on e.processo_digitos = t.processo_digitos
