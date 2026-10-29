{#
  O "Número do TED" do formulário (cd_ted) vem do programa. O portal também o traz
  dentro do código do plano ("30882320220003-000328"), que o modelo usa quando o
  programa ainda não chegou à API. Se os dois divergirem, o plano mudou de programa ou
  um programa passou a ter mais de um plano, e o número mostrado ao gestor deixa de
  identificar o TED.
#}
select c.id_plano_acao, c.cd_ted, p.codigo_plano_acao
from {{ ref("coleta_ted") }} as c
join {{ ref("planos_acao_portal_ted") }} as p on p.id_plano_acao = c.id_plano_acao
where
    c.cd_ted !~ '^[0-9]{14}$'
    or c.cd_ted is distinct from split_part(p.codigo_plano_acao, '-', 1)
