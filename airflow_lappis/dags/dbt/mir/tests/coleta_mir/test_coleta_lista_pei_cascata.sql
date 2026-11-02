{#
  A cascata só funciona se cada nível apontar para o nível certo e nenhum ramo terminar
  vazio: objetivo estratégico sem objetivo específico e objetivo específico sem
  indicador/meta deixam o formulário sem opção. Como os seeds são editados à mão, uma
  linha com o pai trocado passaria pelo teste de relationships.
#}
with
    itens as (select * from {{ ref("coleta_lista_pei") }}),

    nivel_errado as (
        select f.chave, 'pai de nivel errado' as problema
        from itens as f
        left join itens as p on p.chave = f.chave_pai
        where
            (f.nivel = 'area' and f.chave_pai is not null and p.nivel is distinct from 'area')
            or (f.nivel = 'objetivo_estrategico' and f.chave_pai is not null)
            or (f.nivel = 'objetivo_especifico' and p.nivel is distinct from 'objetivo_estrategico')
            or (f.nivel = 'indicador_meta' and p.nivel is distinct from 'objetivo_especifico')
    ),

    sem_filho as (
        select p.chave, 'ramo sem filho' as problema
        from itens as p
        left join itens as f on f.chave_pai = p.chave
        where p.nivel in ('objetivo_estrategico', 'objetivo_especifico') and f.chave is null
    ),

    sem_area as (
        select e.chave, 'objetivo especifico sem area' as problema
        from itens as e
        left join itens as a on a.chave = e.chave_area and a.nivel = 'area'
        where e.nivel = 'objetivo_especifico' and a.chave is null
    ),

    coluna_de_outro_nivel as (
        select chave, 'coluna preenchida em outro nivel' as problema
        from itens
        where
            (cd_siorg is not null and nivel <> 'area')
            or (tp_objetivo is not null and nivel <> 'objetivo_estrategico')
            or (chave_area is not null and nivel <> 'objetivo_especifico')
    )

select *
from nivel_errado
union all
select *
from sem_filho
union all
select *
from sem_area
union all
select *
from coluna_de_outro_nivel
