{{ config(materialized="table") }}

with
    programa as (
        select *
        from {{ ref("programa") }}
    )

select *
from programa
where orgao ilike '%' || '{{ var("orgao_mir") }}' || '%'
