-- Falha se alguma NC com numero de transferencia no campo (lado ORIGEM) ficar
-- fora de ted_credito_nc, ou se o modelo trouxer NC que nao existe na origem.
select 'faltando' as problema, count(*) as qtd
from {{ ref("nc_tesouro_mir") }}
where coalesce(dc, 'ORIGEM') = 'ORIGEM' and nc_transferencia <> '-8'
having
    count(*)
    <> (select count(*) from {{ ref("ted_credito_nc") }} where metodo_vinculo = 'campo')

union all

select 'nc inexistente' as problema, count(*) as qtd
from {{ ref("ted_credito_nc") }}
where nc not in (select nc from {{ ref("nc_tesouro_mir") }})
having count(*) > 0
