# Remodelagem fato-dimensão do dbt MIR

**Data:** 2026-09-29
**Projeto dbt:** `airflow_lappis/dags/dbt/mir` (dbt-postgres 1.7)
**Banco de referência:** PostgreSQL 17, database `analytics`
**Consumidor:** Power BI, com três BIs: Convênios/Termos de Fomento, TEDs e Emendas

## 1. Objetivo

Substituir as camadas silver e gold do MIR por:

- uma **silver** com uma entidade de negócio por modelo, no grão natural, já recortada para o MIR e concentrando as regras de negócio. A silver não faz mais joins largos (`convenio.*` repetido em cada tabela filha);
- um **gold** organizado em **três data marts independentes** em esquema estrela: `mir_convenios`, `mir_teds` e `mir_emendas`.

A bronze não muda.

### Fora de escopo

- Contratos (`contratos_dbt`), PPA (`ppa_dbt`) e dados abertos (`dados_abertos_dbt`) continuam como estão. O `ppa_tesouro` (bronze) é só insumo.
- Transferências especiais / "emendas PIX" do TransfereGov (`planos_acoes`, `executor`, `empenhos_especiais`, `ordens_bancarias` etc.). O mart de Emendas cobre só as emendas do SIAFI.
- Indicadores I2, I3, I7 e I9: estão documentados, mas não existem no código desta branch. Quando forem implementados, já leem o novo gold.

## 2. Conceitos de negócio que orientam o modelo

1. **A emenda não é um instrumento, é a origem do recurso.** O instrumento (convênio, termo de fomento ou TED) é financiado **ou** por emenda **ou** por orçamento próprio do MIR. Exceção conhecida: o instrumento de emenda cujo repasse ficou abaixo do mínimo legal de R$ 200 mil (Decreto nº 11.351/2023, art. 10) recebe, por termo aditivo, um complemento de orçamento próprio (RP 2). Ele continua sendo um instrumento de **Emenda**, marcado com `complemento_proprio = true` (casos 965040 e 965084, com municípios; decisão do usuário em 2026-09-29).
2. **O vínculo emenda → instrumento nasce na nota de empenho (NE).** O número do instrumento é extraído por regex dos textos da NE. Cada NE aponta para no máximo um instrumento. Uma emenda pode chegar a vários instrumentos (hoje, de 1 a 9 convênios por emenda). Um instrumento pode receber mais de uma emenda (hoje, 2 casos).
3. **Existe uma fonte única de execução orçamentária.** Todas as NEs de emenda (221/221) e todas as NEs de TED (679/679) já estão em `siafi_dbt.ppa_tesouro`. O `tg_emendas` serve só para atribuir a emenda a cada NE; os valores vêm sempre do `ppa_tesouro`. Assim uma NE nunca é somada duas vezes.

## 3. Camadas e schemas

| Camada | Schema | Responsabilidade |
|---|---|---|
| Bronze | inalterado (`siconv_dbt`, `siafi_dbt`, `emendas`, `dados_abertos`) | cópia tipada da origem |
| Silver | `mir_silver` | uma entidade por modelo, recorte do MIR, regras de negócio |
| Gold | `mir_convenios`, `mir_teds`, `mir_emendas` | dimensões e fatos consumidas pelo Power BI |

## 4. Convenções do gold

- **Chave substituta:** `sk_<dimensao>` do tipo `bigint`, derivada deterministicamente da chave natural:
  `('x' || substr(md5(<chave natural>), 1, 16))::bit(64)::bigint`, implementada em uma macro `surrogate_key(cols)`. Não usa sequência nem pacote externo, e a chave é estável entre execuções.
- **Chave de tempo:** `sk_tempo` é a data no formato `AAAAMMDD` (`bigint`), e não um md5, para que a chave seja legível e ordenável; `-1` quando a data é nula. A fato calcula as chaves com as mesmas macros da dimensão, sem join; o teste `relationships` garante que cada chave existe.
- **Membro "não identificado":** toda dimensão tem uma linha `sk = -1` com rótulo `Não identificado`. Nenhuma FK de fato fica nula.
- **Datas:** cada fato se liga à `dim_tempo` só pela data do próprio evento (relacionamento ativo único no Power BI). Datas de assinatura e vigência são atributos da dimensão do instrumento.
- **Parlamentar em SCD2:** `dim_parlamentar` tem uma linha por parlamentar × cargo × partido (`valido_de` = primeira filiação, `valido_ate` = última desfiliação, nulo se aberta). A fato recebe o partido vigente na data de emissão da NE (`mir_silver.emenda_ne`), preservando as prioridades 1/2/3 do `emendas_partidos` atual; o fim de filiação em aberto é tratado como `infinity`, sem `current_date`.
- **LGPD:** CPF de pessoa física aparece mascarado nas dimensões de favorecido/fornecedor. O SICONV já publica o CPF mascarado (`***12345***`), então a chave do fornecedor PF é documento mascarado + nome (os 5 dígitos visíveis sozinhos colidem entre pessoas); CPF que chegue sem máscara é mascarado no mesmo formato.
- **Dimensões repetidas entre marts** (tempo, UG, ação/PTRES, natureza, fonte, parlamentar, emenda) são geradas por **macros** dbt compartilhadas. A regra fica em um lugar e cada mart materializa a sua cópia, então os marts são independentes no Power BI.
- **Seed:** `seeds/uf_regiao.csv` (UF → nome da UF e região) alimenta `dim_localidade`. O nome do município e o código IBGE já vêm da proposta, então o cadastro completo de municípios não é necessário.

## 5. Silver (`mir_silver`)

| Modelo | Grão | Regras que concentra | Fontes (bronze) |
|---|---|---|---|
| `execucao_ne` | linha do `ppa_tesouro` (NE × mês × PTRES × natureza × fonte × PO) | **núcleo**: `codigo_emenda` (via `tg_emendas.ne_ccor`; nulo = recurso próprio); `sistema_instrumento` (SICONV · TED · Não identificado), `nr_instrumento` e `metodo_vinculo` (`info_complementar` · `descricao` · `observacao` · `nao_encontrado`), usando as regex hoje em `numero_transferencia` e `empenhos_por_plano_acao` | `ppa_tesouro`, `tg_emendas`, `num_transf`↔plano |
| `convenio_mir` (o nome `convenio` já é do modelo bronze) | instrumento (`nr_convenio`) | recorte do MIR (UG emitente 810008 ou com NE da UG 810008, regra atual de `convenios_consolidados`); atributos 1:1 da proposta (modalidade, objeto, proponente, município); UGs responsáveis agregadas; `origem_recurso` = Emenda se alguma NE do instrumento em `execucao_ne` tem `codigo_emenda`; Recurso próprio se tem NE e nenhuma é de emenda; **Não identificada** se o instrumento não tem NE no núcleo (418 dos 643 convênios, todos assinados entre 2008 e 2022, antes do período do relatório do Tesouro; decisão do usuário em 2026-09-29); `complemento_proprio` = true quando um instrumento de Emenda também tem NEs de recurso próprio | `convenio`, `proposta`, `execucao_ne` |
| `convenio_movimento_financeiro` | movimento | união de desembolso, ingresso de contrapartida, desbloqueio, pagamento e pagamento de tributo, com `tipo_movimento`, recortada aos convênios do MIR; tipo (PF/PJ) e chave do fornecedor | `desembolso`, `ingresso_contrapartida`, `desbloqueio`, `pagamento`, `pagamento_tributo` |
| `convenio_cronograma` | parcela × mês | responsável (Concedente/Convenente/Rendimento), recorte do MIR | `cronograma_desembolso` |
| `convenio_evento` | evento | `tipo_evento` (mudança de situação, termo aditivo, prorrogação de ofício, solicitação de alteração, solicitação de rendimento), recorte do MIR | `historico_situacao`, `termo_aditivo`, `prorroga_oficio`, `solicitacao_alteracao`, `solicitacao_rendimento_aplicacao` |
| `convenio_contagens` | instrumento | quantidades e valores de metas, licitações e empenhos registrados no SICONV, data de fim da primeira meta, data do último desembolso | `meta_crono_fisico`, `licitacao`, `empenho`, `desembolso` |
| `plano_acao_ted` | plano de ação | plano + atributos do programa; `num_transf`; `origem_recurso` | `planos_acao_ted`, `programas_ted`, `execucao_ne` |
| `ted_credito_nc` | movimento de NC | reconstrução da NC SIAFI (`LPAD(ug,6)+LPAD(gestao,5)+ano+'NC'+LPAD(seq,6)`); ponte `num_transf` → plano; sinal/tipo pelo evento (Recebido · Devolvido · Anulado) | `nc_tesouro_mir`, `pf_ptres`, `notas_de_credito` |
| `ted_programacao_pf` | movimento de PF | união `pf_tesouro` + `pf_transfere`; tipo pela `pf_acao` (Transferência · Devolução · Cancelamento) | `pf_tesouro`, `pf_transfere`, `planos_acao_ted` |
| `emenda_dotacao` | emenda × PTRES × natureza × localizador × mês | dotação inicial e atualizada | `tg_emendas_dotacao` |
| `emenda_ne` | NE de emenda | emenda (código, descrição, autor) e parlamentar autor com o partido vigente na data de emissão da NE (prioridades 1/2/3 do `emendas_partidos`) | `tg_emendas`, `execucao_ne`, `parlamentares_historico` (via `ref`) |

Regras gerais da silver:

- **Sem ciclo de dependência:** `execucao_ne` não lê `convenio` nem `plano_acao_ted`; só identifica o sistema e o número do instrumento. A modalidade (Convênio, Fomento, Colaboração, Parceria) vem de `convenio`, que por sua vez lê `execucao_ne` para derivar `origem_recurso`. Ordem: `execucao_ne` → `convenio` / `plano_acao_ted` → gold.

- Nenhum modelo repete colunas de outra entidade; a ligação é pela chave de negócio.
- O recorte do MIR é aplicado **antes** de qualquer join. O SICONV bronze tem o governo inteiro (por exemplo, 7,3 mi de pagamentos e 8,9 mi de linhas de histórico) e o MIR tem 643 instrumentos. O filtro fica dentro de cada ramo, subconsulta e agregação, não num join no fim.
- **Nada que dependa da data de hoje:** a silver guarda datas (fim da primeira meta, último desembolso, fim de vigência), nunca marcações como meta expirada, `vigente` ou dias sem desembolso. O gold ou o Power BI calcula a marcação com a data de referência explícita, para que o dado não mude sozinho a cada rodada noturna (decisão do usuário em 2026-09-29).
- Materialização `table`.

## 6. Gold: mart de Convênios e Termos de Fomento (`mir_convenios`)

Um único conjunto para todas as modalidades do SICONV. Substitui `resumo_convenios` e `resumo_termos_fomento`.

### Dimensões

| Dimensão | Grão | Atributos |
|---|---|---|
| `dim_convenio` | `nr_convenio` | modalidade, origem do recurso, `complemento_proprio`, objeto, situação e subsituação, flags de inadimplente/rescindido/anulado, datas de assinatura, publicação e vigência (original e atual), fim da primeira meta, `vigente` e `meta_expirada` calculados contra `data_referencia` (data da carga, exposta na dimensão), UG(s) responsável(eis), número do processo |
| `dim_convenente` | CNPJ do proponente | nome, natureza jurídica |
| `dim_localidade` | município IBGE | município, UF, região; linhas só com UF quando falta município |
| `dim_fornecedor` | CPF/CNPJ | nome, PF/PJ, documento mascarado quando PF |
| `dim_tempo` | dia | ano, semestre, trimestre, mês, nome do mês, ano-mês |
| `dim_unidade_gestora` | código UG | nome |
| `dim_acao_orcamentaria` | PTRES | programa, ação, plano orçamentário, função, subfunção |
| `dim_natureza_despesa` | natureza | descrição, GND, modalidade de aplicação |
| `dim_fonte_recurso` | fonte detalhada | descrição |
| `dim_emenda` | código da emenda | número, ano, texto do autor |
| `dim_parlamentar` | SCD2 | nome, cargo, partido, UF, foto, logo |

### Fatos

| Fato | Grão | Medidas | FKs |
|---|---|---|---|
| `fato_execucao_orcamentaria` | linha de `execucao_ne` com instrumento do SICONV do universo `convenio_mir` | empenhado, liquidado, pago, RAP inscrito, RAP pago | convênio, tempo, UG, ação, natureza, fonte, emenda, parlamentar |
| `fato_fluxo_financeiro` | movimento | valor; `tipo_movimento` degenerado | convênio, tempo, fornecedor (`-1` quando não há) |
| `fato_cronograma_desembolso` | parcela × mês | valor previsto; responsável degenerado | convênio, tempo |
| `fato_evento_convenio` | evento | quantidade, valor, dias; `tipo_evento` e situação degenerados | convênio, tempo |
| `fato_convenio_posicao` | instrumento (snapshot acumulado) | valor firmado inicial e atualizado, repasse e contrapartida previstos, desembolsado, saldo em conta, contrapartida depositada, desbloqueado/bloqueado, empenhado registrado no SICONV (histórico completo, mesma medida do gold antigo), empenhado/liquidado/pago/RAP das NEs do núcleo SIAFI (só os exercícios do relatório do Tesouro; nulo sem NE), pago a fornecedores, tributos, qtde de desembolsos/pagamentos/empenhos/metas/licitações/aditivos/prorrogações, data do último desembolso e do último pagamento. Os "dias sem repasse" do gold antigo não entram: o BI calcula a partir da data do último desembolso | convênio, convenente, localidade |

## 7. Gold: mart de TEDs (`mir_teds`)

Substitui `ted_resumo_orcamentario` e `ted_empenhos_plano_acao`.

### Dimensões

| Dimensão | Grão | Atributos |
|---|---|---|
| `dim_plano_acao` | `id_plano_acao` | objeto, justificativa, situação, ano, vigência, `vigente`, forma de execução, `num_transf`, `sq_instrumento`, origem do recurso; programa achatado (código, nome, ano, situação, unidade de acompanhamento, flags de autorização) |
| `dim_unidade_executora` | UG descentralizada | sigla, nome |
| `dim_tempo`, `dim_unidade_gestora`, `dim_acao_orcamentaria`, `dim_natureza_despesa`, `dim_fonte_recurso`, `dim_emenda`, `dim_parlamentar` | como em §6 | |

### Fatos

| Fato | Grão | Medidas |
|---|---|---|
| `fato_credito_descentralizado` | movimento de NC | valor; `tipo` (Recebido · Devolvido · Anulado) |
| `fato_programacao_financeira` | movimento de PF | valor; `tipo` (Transferência · Devolução · Cancelamento) |
| `fato_execucao_orcamentaria` | linha de `execucao_ne` com instrumento TED | empenhado, anulado, liquidado, pago, RAP inscrito, RAP pago |
| `fato_plano_acao_posicao` | plano de ação (snapshot) | valor firmado, crédito recebido/devolvido, empenhado, anulado, liquidado, pago no exercício, pago de RAP, RAP inscrito, financeiro recebido/devolvido/cancelado |

A posição tem **uma linha por plano**. Isso corrige o problema atual do grão plano × `num_transf`, em que o `valor_firmado` aparecia em uma só linha e inflava os totais somados.

Limitação conhecida: o vínculo NE → plano depende do `num_transf` na descrição do empenho (hoje, 30 de 118 planos). NEs sem plano aparecem como `Não identificado`, sem ser descartadas.

## 8. Gold: mart de Emendas (`mir_emendas`)

Substitui `emendas_execucao_por_ug`, `emendas_instrumentos_execucao` e `resumo_emendas_orcamento_execucao`.

### Dimensões

| Dimensão | Grão | Atributos |
|---|---|---|
| `dim_emenda` | código da emenda | número, ano, texto do autor |
| `dim_parlamentar` | SCD2 | nome, cargo, partido, UF, foto, logo |
| `dim_instrumento_executor` | tipo + número | tipo (Convênio · Fomento · Colaboração · Parceria · TED · Convênio de outro órgão · Execução direta / não identificado), número, objeto, situação |
| `dim_favorecido` | CPF/CNPJ do empenho | nome, PF/PJ, documento mascarado quando PF |
| `dim_localidade` | localizador do gasto | UF, município quando houver |
| `dim_tempo`, `dim_unidade_gestora`, `dim_acao_orcamentaria`, `dim_natureza_despesa`, `dim_fonte_recurso` | como em §6 | |

### Fatos

| Fato | Grão | Medidas |
|---|---|---|
| `fato_execucao_orcamentaria` | linha de `execucao_ne` com `codigo_emenda` não nulo | empenhado, liquidado, pago, RAP inscrito, RAP pago |
| `fato_dotacao` | linha de `emenda_dotacao` | dotação inicial, dotação atualizada |
| `fato_emenda_posicao` | emenda (snapshot) | dotação atualizada, empenhado, liquidado, pago, qtde de instrumentos |

O instrumento de cada emenda é registrado na NE (`execucao_ne.sistema_instrumento`/`nr_instrumento`) e chega ao mart pela FK `sk_instrumento_executor`. A `dim_instrumento_executor` completa tipo, objeto e situação com `mir_silver.convenio` (modalidade) e `mir_silver.plano_acao_ted`. Nos marts de Convênios e TEDs, a mesma coluna aparece como `sk_emenda` na fato de execução.

Instrumentos do SICONV fora do universo `convenio_mir`: 24 convênios de outros órgãos (FUNAD, UFRJ, UFRGS, UFSM, UERJ, AGU, Ministério das Mulheres) aparecem no núcleo por NEs de outras UGs no relatório do MIR (145 linhas, R$ 13,7 mi empenhados, R$ 0,9 mi de emenda). Ficam fora do mart de Convênios; no mart de Emendas entram na `dim_instrumento_executor` com tipo "Convênio de outro órgão" (decisão do usuário em 2026-09-29).

## 9. Migração do indicador I1

- `dags/indicadores/mir/i1_valor_executado_dag.py`: o `FONTES` passa a ler `mir_teds.fato_plano_acao_posicao` + `mir_teds.dim_plano_acao` (e as fatos de NC, PF e execução necessárias para `classificar_etapa_cadeia`), `mir_convenios.fato_convenio_posicao` + `dim_convenio` + `dim_convenente` + `dim_localidade`, e a origem do recurso via `dim_convenio`/`dim_plano_acao`.
- `plugins/indicadores/i1_valor_executado.py`: ajuste dos nomes de colunas; a lógica de cálculo não muda.
- **Critério de aceite:** os 25 testes de `tests/test_plugins/test_indicadores_i1.py` passam, incluindo a comparação com os CSVs validados pela BI (`fixtures/i1/*.csv`). O ajuste dos testes se limita ao formato das entradas; os valores esperados não mudam.

## 10. Remoção (substituição direta)

Na etapa final, depois da paridade comprovada, são removidos:

- `siconv_dbt/silver/*` (25 modelos) e `siconv_dbt/gold/*`;
- `empenhos_ted_dbt/silver/*`, `empenhos_ted_dbt/views/*` e `empenhos_ted_dbt/gold/*`;
- `emendas_dbt/silver/*` e `emendas_dbt/gold/*`;
- os blocos correspondentes em `schema.yml` e as tabelas órfãs no banco (`drop table` explícito, listado no plano).

A bronze desses domínios e `dados_abertos_dbt/silver/parlamentares_historico` permanecem.

## 11. Testes

| Tipo | Onde | O quê |
|---|---|---|
| Chaves | todos os `dim_*` | `unique` e `not_null` em `sk_*`; existência do membro `-1` |
| Integridade referencial | todos os `fato_*` | `relationships` de cada FK para a dimensão; FK nunca nula |
| Grão | todas as fatos e posições | `unique` na combinação que define o grão |
| Reconciliação | teste singular | soma de empenhado/liquidado/pago de `execucao_ne` = `ppa_tesouro` recortado |
| Consistência entre marts | teste singular | empenhado com origem Emenda em `mir_convenios` + `mir_teds` + execução direta em `mir_emendas` = empenhado total de `mir_emendas` |
| Complemento próprio | teste singular de aviso | lista instrumentos de Emenda com NEs de recurso próprio (`complemento_proprio`); linha de base 2 (965040, 965084). Aviso, não erro: o caso é legítimo, mas um número crescente merece revisão |
| Cobertura do vínculo | teste singular com limite | % de NEs com `metodo_vinculo = 'nao_encontrado'` não maior que a linha de base medida na etapa 1 (o valor fica fixado no teste e só sobe com justificativa no PR) |
| Paridade (temporário) | análise dbt | posição nova × gold antigo, instrumento a instrumento; roda antes da remoção e é apagada depois |
| Indicador | pytest | suíte do I1 verde |

## 12. Ordem de entrega

1. Macros (`surrogate_key`, geradores das dimensões compartilhadas, membro `-1`), seed do IBGE, `mir_silver.execucao_ne` e testes de reconciliação.
2. Mart `mir_convenios` (silver de convênio + gold) com paridade contra `resumo_convenios`/`resumo_termos_fomento`.
3. Mart `mir_teds` com paridade contra `ted_resumo_orcamentario`.
4. Mart `mir_emendas` com paridade contra os golds de emendas e o teste de consistência entre marts.
5. Migração do I1, remoção dos modelos e tabelas antigos e atualização do `dbt_project.yml`.

Cada etapa só avança com `dbt build` verde para os modelos da etapa.

## 13. Riscos

- **Divergência de números na paridade:** alguns resultados atuais têm efeitos colaterais conhecidos (inflação por grão no TED, `union distinct` em `convenios_consolidados`). Toda diferença encontrada é classificada como *bug antigo corrigido* ou *regressão*, e só a segunda bloqueia a etapa. As diferenças aceitas são registradas no PR.
- **Painéis Power BI existentes** que leem os golds antigos quebram na remoção (etapa 5). A lista dos painéis afetados precisa ser confirmada com a equipe antes da etapa 5.
- **Join por nome do parlamentar** continua sujeito a grafias divergentes, como hoje. O modelo não piora nem resolve esse ponto.
- **Reinscrição de restos a pagar** (regra do usuário, generalizada em 2026-09-29). O saldo não pago de uma NE reaparece como inscrito no exercício seguinte: a reinscrição é sempre o mesmo dinheiro (inscrição anterior menos pagamentos e cancelamentos; confirmado nos 164 casos do dump). `execucao_ne.reinscricao_rap` marca essas linhas. As fatos e posições somam RAP inscrito acumulado só com `reinscricao_rap = false` (remove R$ 12,2 mi de dupla contagem no dump); o saldo de RAP de um exercício usa todas as inscrições daquele ano. O teste de aviso `execucao_ne_reinscricao_rap_saldo` acusa reinscrição maior que o saldo.
