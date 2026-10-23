-- Falha se a lista do PPA repetir (nivel, codigo). Codigo repetido viraria
-- opcao duplicada no formulario do Coleta MIR.
select nivel, codigo, count(*) as linhas
from {{ ref("coleta_lista_ppa") }}
group by nivel, codigo
having count(*) > 1
