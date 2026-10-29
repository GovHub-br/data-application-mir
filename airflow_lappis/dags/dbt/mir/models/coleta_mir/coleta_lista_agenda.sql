{{ config(materialized="table") }}

{#
  Contrato do Coleta MIR, itens 3.1 (agendas transversais) e 3.2 (ODS) do formulário de
  TEDs: o catálogo nacional de agendas do PPA, e não só as agendas dos programas do MIR
  (agenda_filtrado_mir), porque o formulário oferece todas.

  agenda transversal -> subagenda (o tipo da subagenda é o nome da agenda mãe)
  ODS -> meta ODS (o catálogo só traz as metas que o PPA usa; as do ODS 18 vêm todas)

  Só entram as revisões a partir de 2025: em 2025 o SIOP recodificou as agendas, e de
  2025 para 2026 os códigos não mudaram. O nome dos ODS vem do seed ods, porque o
  catálogo só traz "ODS 18". Quem saiu da última revisão fica com in_vigente = false.
#}
with
    catalogo as (
        select codigo, tipo, nome, descricao, ano_ppa
        from {{ ref("agenda") }}
        where ano_ppa >= 2025
    ),

    revisao as (select max(ano_ppa) as ano_ppa from catalogo),

    nos as (
        select
            'agenda_transversal' as nivel,
            codigo,
            'agenda:' || codigo as chave,
            cast(null as text) as chave_pai,
            nome,
            descricao,
            ano_ppa
        from catalogo
        where tipo = 'Agenda Transversal'

        union all

        select
            'subagenda',
            s.codigo,
            'agenda:' || s.codigo,
            'agenda:' || m.codigo,
            s.nome,
            s.descricao,
            s.ano_ppa
        from catalogo as s
        join
            catalogo as m
            on m.tipo = 'Agenda Transversal'
            and m.nome = s.tipo
            and m.ano_ppa = s.ano_ppa

        union all

        select
            'meta_ods',
            codigo,
            'agenda:' || codigo,
            'ods:' || substring(tipo from '[0-9]+'),
            nome,
            descricao,
            ano_ppa
        from catalogo
        where tipo like 'ODS %'
    ),

    ultima as (select distinct on (chave) * from nos order by chave, ano_ppa desc)

select
    ('ods:' || o.numero)::text as chave,
    'ods'::text as nivel,
    o.numero::text as codigo,
    cast(null as text) as chave_pai,
    ('ODS ' || o.numero || ' - ' || o.nome)::text as nome,
    cast(null as text) as descricao,
    true as in_vigente
from {{ ref("ods") }} as o

union all

select
    u.chave::text,
    u.nivel::text,
    u.codigo::text,
    u.chave_pai::text,
    u.nome::text,
    u.descricao::text,
    (u.ano_ppa = r.ano_ppa)::boolean
from ultima as u
cross join revisao as r
