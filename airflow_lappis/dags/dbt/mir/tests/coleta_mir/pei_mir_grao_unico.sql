-- Falha se o seed do PEI repetir (nivel, codigo). A lista vira opcoes do
-- formulario do Coleta MIR; codigo repetido duplicaria opcoes.
select nivel, codigo, count(*) as linhas
from {{ ref("pei_mir") }}
group by nivel, codigo
having count(*) > 1
