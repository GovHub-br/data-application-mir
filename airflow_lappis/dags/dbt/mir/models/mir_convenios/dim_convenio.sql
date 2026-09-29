-- Dimensao do convenio: atributos do instrumento, situacao e datas. As
-- marcacoes que dependem da data (vigente, meta expirada) sao calculadas contra
-- data_referencia, a data da carga, exposta na propria dimensao. As marcacoes
-- de inadimplente, rescindido e anulado valem se o convenio passou alguma vez
-- pela situacao (mesma regra do gold antigo).
with
    situacoes as (
        select
            nr_convenio,
            bool_or(situacao = 'INADIMPLENTE') as inadimplente,
            bool_or(situacao = 'CONVENIO_RESCINDIDO') as rescindido,
            bool_or(situacao = 'CONVENIO_ANULADO') as anulado
        from {{ ref("convenio_evento") }}
        where tipo_evento = 'Mudança de situação'
        group by nr_convenio
    )

select
    {{ surrogate_key(["c.nr_convenio"]) }} as sk_convenio,
    c.nr_convenio,
    c.modalidade,
    c.origem_recurso,
    c.complemento_proprio,
    c.objeto,
    c.situacao,
    c.subsituacao,
    c.situacao_publicacao,
    c.instrumento_ativo,
    coalesce(s.inadimplente, false) as inadimplente,
    coalesce(s.rescindido, false) as rescindido,
    coalesce(s.anulado, false) as anulado,
    c.nr_processo,
    c.ug_emitente,
    c.ug_responsavel_codigo,
    c.ug_responsavel_nome,
    c.data_assinatura,
    c.data_publicacao,
    c.data_inicio_vigencia,
    c.data_fim_vigencia,
    c.data_fim_vigencia_original,
    c.data_limite_prestacao_contas,
    k.data_fim_primeira_meta,
    current_date as data_referencia,
    coalesce(c.data_fim_vigencia >= current_date, false) as vigente,
    coalesce(k.data_fim_primeira_meta < current_date, false) as meta_expirada
from {{ ref("convenio_mir") }} as c
left join situacoes as s on s.nr_convenio = c.nr_convenio
left join {{ ref("convenio_contagens") }} as k on k.nr_convenio = c.nr_convenio

union all

select
    -1::bigint,
    '-1',
    'Não identificado',
    'Não identificada',
    false,
    'Não identificado',
    'Não identificado',
    null,
    null,
    null,
    false,
    false,
    false,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    null,
    current_date,
    false,
    false
