-- Falha se o universo de convenios do MIR divergir da regra de recorte:
-- ug_emitente 810008 ou com NE da UG 810008 vinculada no nucleo.
with
    esperado as (
        select nr_convenio
        from {{ ref("convenio") }}
        where ug_emitente = 810008

        union

        select nr_instrumento as nr_convenio
        from {{ ref("execucao_ne") }}
        where sistema_instrumento = 'SICONV' and ug_emitente_codigo = '810008'
    )

select e.nr_convenio, 'faltando em convenio_mir' as problema
from esperado as e
left join {{ ref("convenio_mir") }} as c on c.nr_convenio = e.nr_convenio
where c.nr_convenio is null

union all

select c.nr_convenio, 'fora do recorte' as problema
from {{ ref("convenio_mir") }} as c
left join esperado as e on e.nr_convenio = c.nr_convenio
where e.nr_convenio is null
