# Migração dos painéis do MIR para os novos data marts

O dbt do MIR passou a publicar três data marts em esquema estrela, um por BI:
`mir_convenios`, `mir_teds` e `mir_emendas`. As tabelas antigas de silver e
gold listadas abaixo saíram do dbt: continuam no banco, mas **não são mais
atualizadas**. Depois de migrar os painéis, elas são removidas pelo script
`docs/mir-drop-legado.sql`.

## Como os marts funcionam

- Cada mart tem **dimensões** (`dim_*`, uma linha por coisa: convênio, plano de
  ação, emenda, parlamentar, UG, data...) e **fatos** (`fato_*`, uma linha por
  evento ou por posição, só com chaves `sk_*` e valores).
- No Power BI, relacione cada `sk_*` da fato com a dimensão de mesmo nome
  (relação um-para-muitos, filtro da dimensão para a fato). Toda dimensão tem
  a linha `-1` "Não identificado", então nenhuma chave fica vazia.
- As fatos `fato_*_posicao` têm uma linha por instrumento (ou por emenda) com
  os valores acumulados. Use-as para cartões e tabelas de resumo.
- As fatos de movimento (execução, fluxo financeiro, crédito, dotação) têm uma
  linha por evento com data (`sk_tempo`, ligada à `dim_tempo`). Use-as para
  séries no tempo.
- Restos a pagar inscritos: some `restos_a_pagar_inscritos_acumulavel`. A
  coluna `restos_a_pagar_inscritos` repete o saldo reinscrito a cada ano e só
  serve para ver o saldo de um exercício.

## Tabela antiga → onde está agora

### Convênios e termos de fomento (`siconv_dbt` → `mir_convenios`)

| Tabela antiga | Onde está agora |
|---|---|
| `resumo_convenios`, `resumo_termos_fomento` | `fato_convenio_posicao` + `dim_convenio` (a `modalidade` separa convênio e termo), `dim_convenente`, `dim_localidade` |
| `convenios_consolidados`, `termo_fomento_consolidado`, `proposta_convenio`, `convenio_proposta` | `dim_convenio`, `dim_convenente`, `dim_localidade` |
| `convenio_desembolso`, `convenio_ingresso_contrapartida`, `convenio_desbloqueio`, `convenio_pagamento`, `convenio_pagamento_tributo`, `convenio_proposta_pagamento` | `fato_fluxo_financeiro` (coluna `tipo_movimento`) + `dim_fornecedor` |
| `convenio_cronograma_desembolso`, `proposta_cronograma_desembolso`, `meta_cronograma_desembolso` | `fato_cronograma_desembolso` |
| `convenio_historico_situacao`, `proposta_historico_situacao`, `convenio_termo_aditivo`, `convenio_prorroga_oficio`, `convenio_solicitacao_alteracao`, `convenio_solicitacao_rendimento` | `fato_evento_convenio` (coluna `tipo_evento`) |
| `convenio_empenho` | empenhos do SICONV: `valor_empenhado_siconv` e `qtd_empenhos_siconv` em `fato_convenio_posicao`; execução do SIAFI por NE: `fato_execucao_orcamentaria` |
| `convenio_meta_crono_fisico`, `proposta_meta_crono_fisico`, `convenio_licitacao` | quantidades e valores em `fato_convenio_posicao` (`qtd_metas`, `qtd_licitacoes`, `valor_licitado`); `data_fim_primeira_meta` e `meta_expirada` em `dim_convenio` |
| `emendas_convenio` | `fato_execucao_orcamentaria` com `dim_emenda` e `dim_parlamentar` (NEs de emenda do convênio) |
| `numero_transferencia` | sem tabela equivalente: o vínculo NE → convênio já está em `fato_execucao_orcamentaria` (`sk_convenio`) |

### TEDs (`siafi_dbt` → `mir_teds`)

| Tabela antiga | Onde está agora |
|---|---|
| `ted_resumo_orcamentario` | `fato_plano_acao_posicao` + `dim_plano_acao` |
| `ted_empenhos_plano_acao`, `empenhos_por_plano_acao` | `fato_execucao_orcamentaria` |
| `nc_plano_acao`, `nc_unificado` | `fato_credito_descentralizado` |
| `pf_unificado`, `pf_unificado_planos_acao` | `fato_programacao_financeira` |
| `num_transf_n_plano_acao` (view) | coluna `num_transf` de `dim_plano_acao` |

### Emendas (`emendas` → `mir_emendas`)

| Tabela antiga | Onde está agora |
|---|---|
| `resumo_emendas_orcamento_execucao`, `emendas_orcamento_execucao` | `fato_emenda_posicao` (uma linha por emenda); por data: `fato_execucao_orcamentaria` e `fato_dotacao` |
| `emendas_partidos` | `dim_parlamentar` (uma linha por parlamentar × cargo × partido, com `valido_de`/`valido_ate`); a fato já traz o partido da data da NE |
| `instrumentos_emendas`, `emendas_instrumentos_execucao` | `dim_instrumento_executor` + `fato_execucao_orcamentaria` |
| `emendas_execucao_por_ug` | `fato_execucao_orcamentaria` + `dim_unidade_gestora` |

`emendas.planos_partidos` (planos de ação das transferências especiais) **não
muda**.

## Números que mudam de propósito

- **Convênios:** `resumo_convenios` tinha convênios repetidos (834 linhas para
  643 convênios). Somas feitas direto nela ficavam de 32% a 52% acima do real.
  Os marts têm um convênio por linha, então os totais novos são menores.
- **Restos a pagar inscritos:** a soma antiga contava a reinscrição do mesmo
  saldo a cada ano. O acumulado novo não conta (R$ 12,2 mi a menos no dump).
- **Origem do recurso:** vem das notas de empenho. Instrumentos com NE de
  emenda são "Emenda" mesmo sem parlamentar registrado no SICONV.
- **TEDs:** o vínculo das NEs, NCs e PFs com o plano cobre casos que o modelo
  antigo perdia e não conta mais as NCs internas do MIR (238012 → 810008).
- **Indicador I1** (`indicadores.i1_*`): passa a ler os marts. Na saída
  `i1_ted_por_instrumento`, a coluna `n_linhas_resumo` virou `qtd_nes`
  (quantidade de NEs do plano).

## Ordem sugerida

1. Para cada painel, listar as tabelas antigas que ele lê (Power Query →
   Fonte) e trocar pelas do mart, conforme as tabelas acima.
2. Conferir os totais do painel com os números que mudam de propósito.
3. Quando nenhum painel ler mais as tabelas antigas, rodar
   `docs/mir-drop-legado.sql`. Se uma view ou outro objeto do banco ainda
   depender delas, o script falha sem apagar nada. Um painel do Power BI **não**
   impede o drop: o painel que ainda ler uma tabela antiga quebra.
