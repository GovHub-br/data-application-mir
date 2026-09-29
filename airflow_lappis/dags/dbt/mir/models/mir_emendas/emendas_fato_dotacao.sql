{{ config(alias="fato_dotacao") }}

-- Dotacao das emendas, um movimento por linha (lancamentos positivos e
-- negativos; a soma e a dotacao do periodo). O parlamentar e o autor vigente na
-- data do movimento.
select
    d.id_movimento,
    {{ fk(["d.codigo_emenda"]) }} as sk_emenda,
    {{ fk(["d.id_parlamentar", "d.cargo_parlamentar", "d.sigla_partido"]) }}
    as sk_parlamentar,
    {{ sk_tempo("d.data_movimento") }} as sk_tempo,
    {{ fk(["d.ptres"]) }} as sk_acao_orcamentaria,
    {{ fk(["d.natureza_despesa"]) }} as sk_natureza_despesa,
    {{ fk(["d.fonte_recursos_detalhada"]) }} as sk_fonte_recurso,
    {{ fk(["d.localizador_gasto"]) }} as sk_localidade,
    d.modalidade_aplicacao,
    d.dotacao_inicial,
    d.dotacao_atualizada
from {{ ref("emenda_dotacao") }} as d
