-- Falha se o vinculo NE -> convenio violar suas regras:
-- * nr_convenio so pode vir preenchido quando ha exatamente um candidato;
-- * NE ambigua (mais de um candidato) nao pode escolher um convenio;
-- * todo nr_convenio precisa existir no cadastro do SICONV.
select ne_ccor, 'nr_convenio sem candidato unico' as problema
from {{ ref("vinculo_ne_convenio") }}
where qtd_convenios = 1 and nr_convenio is null

union all

select ne_ccor, 'ambigua com convenio escolhido' as problema
from {{ ref("vinculo_ne_convenio") }}
where qtd_convenios > 1 and nr_convenio is not null

union all

select v.ne_ccor, 'convenio inexistente no SICONV' as problema
from {{ ref("vinculo_ne_convenio") }} as v
left join {{ ref("convenio") }} as c on c.nr_convenio = v.nr_convenio
where v.nr_convenio is not null and c.nr_convenio is null
