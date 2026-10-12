{{ config(materialized="table") }}

{#
  Grão de empenho vinculado a TED/NC: o que a cascata de extração de num_transf
  conseguiu ligar. A cascata em si vive em empenhos_ted_cascata (ephemeral, nada
  descartado); aqui ficam apenas o filtro de vínculo e a resolução do plano de
  ação, para que o descarte seja um passo explícito e mensurável.

  Issue #508: o filtro abaixo elimina linhas, e é por isso que ele agora está
  isolado. Quem chega sem nc e sem num_transf (bucket 'vinculo nao encontrado')
  não entra na gold. `nc != ''` não é null-safe de propósito — comportamento
  preservado da versão monolítica: com nc nulo a condição vira NULL, então a NE
  só sobrevive se tiver num_transf ou se for uma exclusão SICONV rotulada
  (issue #510, mantida visível de propósito). O complemento exato deste filtro,
  categorizado por motivo, está em empenhos_ted_residuo.
#}

with
    planos_de_acao as (
        select * from {{ ref("num_transf_n_plano_acao") }} where plano_acao is not null
    ),

    empenhos_restantes_metodo_9 as (
        select *
        from {{ ref("empenhos_ted_cascata") }}
        where (nc != '')
            or (num_transf is not null)
            or metodo = 'excluido: numero e de convenio/termo de fomento (SICONV)'
    ),

    result_table as (
        select distinct
            er.*,
            pa.plano_acao::integer as plano_acao,
            pa.num_transf as num_transf_pa
        from empenhos_restantes_metodo_9 er
        left join planos_de_acao pa on er.num_transf = cast(pa.num_transf as text)
    )

select *
from result_table
