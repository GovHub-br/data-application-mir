-- Falha se o instrumento vinculado a uma NE nao existir no cadastro de origem,
-- ou se sistema_instrumento e nr_instrumento estiverem incoerentes.
select e.ne_ccor, 'TED sem plano de acao' as problema
from {{ ref("execucao_ne") }} as e
left join {{ ref("planos_acao_ted") }} as p on p.id_plano_acao::text = e.nr_instrumento
where e.sistema_instrumento = 'TED' and p.id_plano_acao is null

union all

select e.ne_ccor, 'SICONV sem convenio' as problema
from {{ ref("execucao_ne") }} as e
left join {{ ref("convenio") }} as c on c.nr_convenio = e.nr_instrumento
where e.sistema_instrumento = 'SICONV' and c.nr_convenio is null

union all

select e.ne_ccor, 'Nao identificado com numero' as problema
from {{ ref("execucao_ne") }} as e
where e.sistema_instrumento = 'Não identificado' and e.nr_instrumento is not null
