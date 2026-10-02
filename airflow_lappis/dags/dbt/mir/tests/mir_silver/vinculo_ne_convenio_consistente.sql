-- Falha se o vinculo NE -> convenio violar suas regras:
-- * candidato unico sempre vira o convenio da NE;
-- * NE com varios candidatos so escolhe convenio pelo desempate de processo;
-- * fonte_vinculo so existe quando ha convenio escolhido;
-- * todo nr_convenio precisa existir no cadastro do SICONV.
select ne_ccor, 'candidato unico sem nr_convenio' as problema
from {{ ref("vinculo_ne_convenio") }}
where qtd_convenios = 1 and nr_convenio is null

union all

select ne_ccor, 'escolha sem desempate por processo' as problema
from {{ ref("vinculo_ne_convenio") }}
where qtd_convenios > 1 and nr_convenio is not null and not desempate_processo

union all

select ne_ccor, 'fonte em NE ambigua' as problema
from {{ ref("vinculo_ne_convenio") }}
where nr_convenio is null and fonte_vinculo is not null

union all

select v.ne_ccor, 'convenio inexistente no SICONV' as problema
from {{ ref("vinculo_ne_convenio") }} as v
left join {{ ref("convenio") }} as c on c.nr_convenio = v.nr_convenio
where v.nr_convenio is not null and c.nr_convenio is null
