{{ config(alias="dim_instrumento_executor") }}

-- Instrumentos que executam as emendas: convenio, fomento, colaboracao ou
-- parceria do MIR, TED, ou convenio de outro orgao. O membro -1 e a execucao
-- direta / nao identificada (NE de emenda sem instrumento encontrado).
select
    {{ surrogate_key(["sistema_instrumento", "nr_instrumento"]) }}
    as sk_instrumento_executor,
    sistema_instrumento,
    nr_instrumento,
    tipo_instrumento,
    objeto,
    situacao,
    executor_nome
from {{ ref("emenda_instrumento") }}

union all

select
    -1::bigint,
    'Não identificado',
    '-1',
    'Execução direta / não identificado',
    null,
    null,
    null
