{{ config(severity="warn") }}

{#
  O universo de coleta_convenio é pela proposta (órgão superior 67000). Este teste olha
  pelo outro lado, o do dinheiro: convênio ou contrato de repasse assinado, com empenho
  de uma UG do MIR desde 2023 e prestação de contas não encerrada, que ficou fora. Pega
  mudança de órgão superior na fonte ou de nome de situação ou modalidade.
#}
with
    empenhado as (
        select distinct e.nr_convenio
        from {{ ref("empenho") }} as e
        inner join {{ ref("ugs_mir") }} as m on m.ug_codigo = e.ug_emitente::text
        where e.data_emissao >= '2023-01-01'
    )

select c.nr_convenio, p.cod_orgao_sup, p.modalidade, c.sit_convenio
from empenhado as e
inner join {{ ref("convenio") }} as c on c.nr_convenio = e.nr_convenio
inner join {{ ref("proposta") }} as p on p.id_proposta = c.id_proposta
left join {{ ref("coleta_convenio") }} as k on k.nr_convenio = c.nr_convenio
where
    k.nr_convenio is null
    and p.modalidade not in ('TERMO DE FOMENTO', 'TERMO DE COLABORACAO', 'TERMO DE PARCERIA')
    and c.dia_assin_conv is not null
    and c.sit_convenio not in (
        'Convênio Anulado',
        'Cancelado',
        'Prestação de Contas Concluída',
        'Prestação de Contas Aprovada',
        'Prestação de Contas Aprovada com Ressalvas',
        'Prestação de Contas Rejeitada'
    )
