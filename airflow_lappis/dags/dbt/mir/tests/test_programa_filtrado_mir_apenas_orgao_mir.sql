-- Falha se programa_filtrado_mir trouxer alguma linha cujo órgão não seja o MIR — o filtro
-- da silver é textual (ilike), então uma mudança de grafia no CSV do PPA/SIOP
-- poderia silenciosamente deixar passar (ou barrar) programas errados.

select *
from {{ ref('programa_filtrado_mir') }}
where orgao not ilike '%' || '{{ var("orgao_mir") }}' || '%'
