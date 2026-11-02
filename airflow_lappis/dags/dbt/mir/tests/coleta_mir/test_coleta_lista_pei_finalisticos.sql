{#
  Os objetivos finalísticos do PEI são exatamente OE1 a OE6, com OE5 e OE6 em linhas
  separadas, embora o PEI numere juntos os objetivos específicos deles. Falha se um deles
  faltar ou se outro objetivo entrar com esse tipo.
#}
with
    esperados as (
        select 'OE' || n as codigo from generate_series(1, 6) as n
    ),

    atuais as (
        select codigo
        from {{ ref("coleta_lista_pei") }}
        where nivel = 'objetivo_estrategico' and tp_objetivo = 'finalistico'
    )

select coalesce(e.codigo, a.codigo) as codigo
from esperados as e
full join atuais as a on a.codigo = e.codigo
where e.codigo is null or a.codigo is null
