{{ config(severity="warn", warn_if=">4") }}

-- Aviso (nao bloqueia a DAG): autores de emenda cujo nome nao foi encontrado em
-- parlamentares_historico (grafia divergente). As NEs deles ficam com
-- parlamentar Nao identificado no gold. Linha de base em 2026-09-29: 4 autores
-- (Augusto Puppio, Guilherme Boulos, Paulao, Reginete Bispo); o aviso so
-- dispara se aparecer um quinto.
select autor_nome, count(*) as qtd_nes
from {{ ref("emenda_ne") }}
where prioridade_match = 3
group by autor_nome
