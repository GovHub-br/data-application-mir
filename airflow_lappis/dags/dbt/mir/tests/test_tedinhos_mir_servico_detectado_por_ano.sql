{{ config(severity="warn") }}

-- Avisa quando um ano com NCs carregadas nao tem nenhum instrumento de servico
-- administrativo. O MIR descentraliza para o CSC/MGI todo ano, entao zero indica
-- que a regra parou de disparar -- p.ex. o relatorio do Tesouro Gerencial mudou o
-- formato do favorecido ou da acao (zeros a esquerda, descricao junto do codigo).
-- O relatorio "ate 2025" e o "desde 2026" vem de fontes diferentes; e aviso, nao
-- erro, porque um ano recem-aberto pode ainda nao ter essa NC.
select
    left(right(nc, 12), 4) as ano,
    count(*) as linhas,
    count(*) filter (where servico_administrativo) as linhas_servico
from {{ ref("tedinhos_mir") }}
group by 1
having count(*) filter (where servico_administrativo) = 0
