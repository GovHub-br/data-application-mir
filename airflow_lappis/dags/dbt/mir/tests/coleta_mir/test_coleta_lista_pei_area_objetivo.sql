{#
  Os pares ligam uma área a um objetivo estratégico, e toda área precisa chegar a algum
  objetivo, pelos próprios pares ou pelos da área mãe. É essa a regra documentada para quem
  lê: as diretorias das secretarias finalísticas não têm par próprio no PEI.
#}
with
    itens as (select * from {{ ref("coleta_lista_pei") }}),

    pares as (select * from {{ ref("coleta_lista_pei_area_objetivo") }}),

    par_de_nivel_errado as (
        select p.chave_area as chave, 'par de nivel errado' as problema
        from pares as p
        left join itens as a on a.chave = p.chave_area
        left join itens as o on o.chave = p.chave_objetivo
        where a.nivel is distinct from 'area' or o.nivel is distinct from 'objetivo_estrategico'
    ),

    area_sem_objetivo as (
        select a.chave, 'area sem objetivo' as problema
        from itens as a
        where
            a.nivel = 'area'
            and not exists (
                select 1 from pares as p where p.chave_area in (a.chave, a.chave_pai)
            )
    )

select *
from par_de_nivel_errado
union all
select *
from area_sem_objetivo
