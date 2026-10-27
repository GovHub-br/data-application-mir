-- Falha se um tedinho publicado no gov.br (seed tedinhos_identificados_mir) for
-- classificado como servico administrativo. Complementa o teste de precisao
-- (test_tedinhos_mir_sem_servico_administrativo): aquele garante que servico nao
-- vira tedinho, este que tedinho conhecido nao vira servico. O cruzamento e pelo
-- processo, que tedinhos_mir so extrai das NCs a partir de 2026.
select distinct
    g.ano_publicacao,
    g.orgao_parceiro,
    g.processo,
    t.instrumento_key,
    t.favorecido_doc,
    t.acao_governo
from {{ ref("tedinhos_identificados_mir") }} as g
join {{ ref("tedinhos_mir") }} as t on t.processo = g.processo
where t.servico_administrativo
