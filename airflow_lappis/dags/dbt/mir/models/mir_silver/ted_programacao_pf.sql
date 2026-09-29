{{ config(materialized="table") }}

-- Programacao financeira (PF) dos TEDs do MIR, uma linha por linha do
-- relatorio do Tesouro. O plano vem pela inscricao da PF, que e o numero da
-- transferencia (sq_instrumento do plano). O casamento antigo com o
-- TransfereGov pelo numero da PF nao e usado: o numero sem a UG colide entre
-- UGs. A unidade executora e o lado da PF que nao e o MIR (UG 81xxxx).
with
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
            p.pf,
            p.pf_evento,
            p.pf_acao,
            p.pf_fonte_recursos,
            p.pf_inscricao,
            p.emissao_dia,
            p.pf_valor_linha
        )
    ) as id_movimento,
    p.pf,
    case p.pf_acao when '8' then 'Transferência' when '10' then 'Devolução' end as tipo,
    p.emissao_dia as data_movimento,
    nullif(trim(p.pf_inscricao), '') as num_transf,
    pl.id_plano_acao,
    case
        when p.ug_emitente like '81%' then p.ug_favorecido else p.ug_emitente
    end as ug_executora_codigo,
    case
        when p.ug_emitente like '81%'
        then p.ug_favorecido_descricao
        else p.ug_emitente_descricao
    end as ug_executora_nome,
    p.pf_evento_descricao as evento,
    p.pf_fonte_recursos as fonte_recursos,
    p.pf_valor_linha as valor
from {{ ref("pf_tesouro") }} as p
left join planos as pl on pl.sq_instrumento = nullif(trim(p.pf_inscricao), '')
