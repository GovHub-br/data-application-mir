#!/bin/bash
# Exporta do data warehouse (dump local) as tabelas de referência usadas pela análise.
# Uso: ./exportar_dados.sh [container] [banco]   (padrão: mir-dump-pg17 analytics)
set -e
CONTAINER=${1:-mir-dump-pg17}
BANCO=${2:-analytics}
DESTINO="$(cd "$(dirname "$0")" && pwd)/dados"
mkdir -p "$DESTINO"

exporta() {
    docker exec "$CONTAINER" psql -U postgres -d "$BANCO" -c "\copy ($1) to stdout csv header" > "$DESTINO/$2"
    echo "$2: $(($(wc -l < "$DESTINO/$2") - 1)) linhas"
}

# vínculo NE -> TED da cascata dbt
exporta "select distinct ne_ccor, num_transf, plano_acao, metodo
         from siafi_dbt.empenhos_por_plano_acao" map_ted.csv
# crédito (NC) vinculado a TED
exporta "select extract(year from data_movimento)::int ano, tipo, num_transf, id_plano_acao,
                ug_executora_codigo ug, ptres, fonte_recursos fonte, valor, nc
         from mir_silver.ted_credito_nc" nc.csv
# planos de ação (TransfereGov)
exporta "select num_transf, id_plano_acao, ano, ug_unidade_descentralizada ug_rec,
                sigla_unidade_descentralizada sigla, unidade_descentralizada, objeto,
                justificativa, valor_firmado, situacao
         from mir_silver.ted_plano_acao" pa.csv
# numeração do MIR (página do gov.br)
exporta "select numero_ted, ano_ted, id_plano_acao, num_transf, processo, parceiro
         from mir_silver.ted_gov_br" govbr.csv
# NC -> plano de ação
exporta "select distinct nc, ug_emitente, favorecido_doc, relatorio, id_plano_acao,
                nc_transferencia, emissao_ano
         from siafi_dbt.nc_plano_acao" ncpa.csv
# NCs brutas do SIAFI (inclui as sem nº de transferência = tedinhos). Sem distinct:
# itens idênticos da mesma NC são linhas legítimas. Desde 2026 cada célula vem com
# ORIGEM e DESTINO; o crédito do recebedor é o DESTINO (como na bronze nc_tesouro_mir).
exporta "select nc, nc_transferencia, ptres, fonte_recursos fonte, favorecido_doc fav,
                plano_interno pi, relatorio, movimento_liquido_moeda_origem valor
         from siafi.nc_tesouro_ate_2025" nc_raw1.csv
exporta "select nc, nc_transferencia, ptres, fonte_codigo fonte, favorecido_codigo fav,
                pi_codigo pi, relatorio, valor_celula valor
         from siafi.nc_tesouro_desde_2026 where dc = 'DESTINO'" nc_raw2.csv
