{{ config(severity="warn") }}

-- A teds_gov_br_mir_dag grava um retrato completo das páginas de transferências
-- voluntárias a cada execução, e a bronze serve só o mais recente (max(dt_ingest)).
-- A DAG só falha quando NENHUMA página rende TED, então uma subpágina de ano que
-- pare de render conteúdo — por exemplo porque o portal passou a usar um tipo de
-- bloco que documento_para_texto não conhece — sai do retrato em silêncio, e os
-- TEDs daquele ano desaparecem da bronze e da silver sem erro nenhum. O único
-- sinal hoje é um aviso no log do cliente, que ninguém acompanha.
--
-- Este teste acusa a página que já teve TED em algum retrato e não aparece mais na
-- bronze. O lado de hoje vem da bronze, e não de um filtro por max(dt_ingest)
-- repetido aqui, porque é a bronze que a silver lê: o que importa é a cobertura do
-- que está servido. O lado histórico vem da raw, única que guarda os retratos
-- anteriores.
--
-- A comparação é com o máximo histórico, e não com o retrato anterior, para
-- continuar avisando enquanto o problema durar: avisar uma vez só reproduziria o
-- silêncio que o teste existe para quebrar.
--
-- Não acusa página nova sem TED (o ano que o portal cria antes de publicar o
-- primeiro TED), porque ela nunca teve. Na primeira execução, com um retrato
-- único, devolve zero linhas.
--
-- Limites conhecidos:
--   1. Perda parcial dentro de uma página (alguns blocos ilegíveis, não todos) não
--      aparece aqui, porque a página continua com TED. Vale para
--      descentralizacoes_gov_br também: se os blocos de uma página ficam
--      ilegíveis, os dois lados somem juntos, e o lado dos TEDs já denuncia.
--   2. Página retirada do portal de propósito avisa para sempre, porque o
--      histórico guarda que ela já teve TED. Se isso acontecer, a correção é
--      decidir explicitamente: ou a página voltou e o aviso se resolve, ou ela
--      saiu de vez e este teste precisa de uma exclusão como a de
--      test_coleta_ted_execucao_instrumento_coberto.
with
    historico as (
        select pagina, max(teds) as teds_max
        from
            (
                select dt_ingest, pagina, count(*) as teds
                from {{ source("transfere_gov", "teds_gov_br") }}
                group by dt_ingest, pagina
            ) as r
        group by pagina
    ),

    servido as (select pagina, count(*) as teds from {{ ref("teds_gov_br") }} group by pagina)

select
    h.pagina,
    h.teds_max as teds_ja_vistos,
    coalesce(s.teds, 0) as teds_na_bronze
from historico as h
left join servido as s on h.pagina = s.pagina
where coalesce(s.teds, 0) = 0
