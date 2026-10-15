# Execução dos TEDs do MIR por instrumento

Análise exploratória que abre a consulta oficial do MIR **"Execução TED por UG"**
(Tesouro Gerencial), que vem no grão de UG, por **instrumento**: TED ou tedinho
(descentralização de crédito sem TED registrado no TransfereGov). O valor de cada
instrumento sai das notas de empenho (NE) e soma, no centavo, o valor oficial.

Os scripts são o gabarito para levar as regras para a cascata do dbt
(`empenhos_ted_dbt`). Eles ainda não alteram o pipeline nem o painel.

## Resultado

Empenhado de 2023 a 30/09/2026, em R$ milhões. Fecha no centavo com a consulta
oficial em empenhado, liquidado e pago.

| Ano | Oficial | Cascata dbt | Regras determinísticas | Similaridade | Crédito da UG | Tedinho / subdescentr. | Não identificado |
|---|---|---|---|---|---|---|---|
| 2023 | 32,01 | 17,46 | 9,39 | — | 4,92 | 0,23 | 0,00 |
| 2024 | 72,89 | 38,44 | 18,51 | 9,79 | 6,15 | — | 0,00 |
| 2025 | 80,11 | 40,83 | 14,44 | 5,33 | 18,78 | 0,71 | 0,02 |
| 2026 | 50,12 | 33,97 | 9,82 | 3,22 | 3,08 | 0,03 | 0,01 |
| **Total** | **235,12** | **130,70** | **52,16** | **18,34** | **32,93** | **0,97** | **0,02 (0,01%)** |

São 90 TEDs e 32 tedinhos com execução no período. Sobram 9 NEs sem instrumento
identificado (R$ 23.769,36). 2023 e 2024 fecham 100%.

## Achados que afetam o pipeline

1. **O relatório de NE precisa ser extraído em R$ e sem filtro de saldo.**
   - Os CSVs antigos do relatório "Notas de empenhos por programa PPA" filtravam
     `Saldo - Moeda Origem >= 0,01`. Esse filtro corta as anulações de empenho e
     infla o empenhado (2024: R$ 96,7M contra R$ 72,9M oficiais).
   - A métrica "Moeda Origem" deixa em moeda estrangeira as UGs que pagam no
     exterior: o CNPq 364150 e a UG 240217 do MIR, que aparece no
     `siafi_dbt.ppa_tesouro` atual com R$ 40,5M que, em reais, são R$ 57 mil.
   - Com o relatório em R$ e sem o filtro (`ppa_tesouro(AAAA).csv`), as 444 células
     (ano, UG, ação, PO, PTRES, fonte, grupo) batem 100% com a consulta oficial.
     A DAG `ne_ppa_tesouro_mir_ingest` identifica as colunas pelo código do item,
     então a troca da métrica não quebra a ingestão.
2. **Validar o número do TED.** A cascata extrai números do texto da NE que não são
   TED do MIR. Foram 41 NEs (R$ 12,4M), como o chamamento SENAD/MJSP no Fundo
   Antidrogas e instrumentos da AGU, UFRGS e UFSM. O número só vale se existir como
   plano de ação **ou** tiver NC de crédito vinculada. O segundo critério é
   necessário: o TED 698627 (MIR/INCRA, processo de 2019) não está em
   `ted_plano_acao`, mas tem crédito.
3. **Tedinho tem crédito e pode ser identificado.** NC do MIR com
   `nc_transferencia = -8` é um tedinho. Na página do gov.br ele aparece como
   "Descentralização de Crédito ... Processo: 21290.xxxxxx/AAAA-xx", com valor igual
   ao da NC (ou à soma de duas NCs). `govbr_pagina.py` extrai essas entradas e liga
   cada uma à NC pelo valor, só entre NCs para o órgão do parceiro, e só quando o
   casamento é único: 16 das 18 descentralizações da página; Fiocruz e UFC ficam
   ambíguas (duas NCs de mesmo valor). O tedinho ligado leva o processo no nome. O
   scraper `cliente_transferencias_gov_br.py` só abre bloco em "Termo de Execução
   Descentralizada nº" ou "TED nº" e descarta essas entradas.
4. **NC cancelada e relançada.** É comum o MIR anular uma NC (ou o recebedor
   devolvê-la) e lançar outra, às vezes com outro PTRES ou outra fonte. A
   anulação/devolução abate a NC de itens idênticos (ou, sem isso, a única de mesmo
   valor total ainda não abatida). Se uma NE cita a NC cancelada, ela vai para a NC
   relançada: mesmo órgão, mesmo ano, mesmo valor bruto. Ex.: ENAP 2023, NC000002
   devolvida item por item e relançada como NC000003. Quando a anulação empata em
   valor com duas ou três NCs ainda não abatidas, elas são o mesmo cancela-e-relança
   e viram um instrumento só ("NC_A / NC_B"): UFC 2025 (NC000031/000036), UFF 2025
   (NC000351/000354), Fiocruz 2024. Com isso, as 18 descentralizações da página do
   gov.br ficam ligadas.
5. **Nem toda NC sem número é tedinho.** No INCRA, a NC 810008 2023NC000015 veio
   sem número, mas as NEs citam o TED 698627. Quando o texto da NE cita um TED do
   órgão, ele prevalece sobre a ausência de número na NC.
6. **NC desde 2026: só o lado DESTINO é crédito do recebedor, e o sinal vem do
   tipo.** Em `siafi.nc_tesouro_desde_2026` cada célula vem com ORIGEM (lado do MIR)
   e DESTINO; somar os dois dobra o valor (a bronze `nc_tesouro_mir` já filtra o
   DESTINO). O `valor_celula` vem sempre positivo: anulação e devolução só aparecem
   no `tipo_nc`. Somar sem o sinal conta o estorno como mais crédito (UFF 2026: a
   NC000066, "ESTORNO DE NOTA DE CREDITO 2026NC000064", virava R$ 204 mil a mais). A
   descrição do estorno cita a NC estornada e serve para casar os dois.
7. **A UG que recebe o destaque nem sempre é a que empenha.** A UFF recebe na 153056
   e empenha na 150123, e o CNPq recebe na 364102 e empenha na 364150. Por isso as
   regras de crédito trabalham por órgão.
8. **Há repasse entre órgãos.** O MIR firma o TED com um órgão que repassa o crédito
   a outro pelo TED dele, e a NE do executor cita o número do segundo TED. Ex.: TED
   25/2023 (949807) do MIR com o MinC, repassado à UNIFESP pelo "TED 09/2023,
   transf. 950762" do MinC; TED 955619 do MIR com o MinC, repassado à UNIRIO; e os
   repasses da ENAP e da Palmares à UnB. O órgão intermediário pode nem aparecer na
   consulta oficial (o MinC não executou nada), e o crédito precisa ser mantido
   mesmo para UGs fora dela.

## Método

Cada NE fica com a primeira camada que a resolver.

| Camada | Regra | Validação |
|---|---|---|
| 1 cascata dbt | vínculo de `siafi_dbt.empenhos_por_plano_acao` | — |
| 2 regras | A1 nº do TransfereGov no texto; A2 numeração do MIR ("TED 17/2026") pela página do gov.br; D NC citada; B NE de referência (reforço); C mesmo processo; E mesmo contrato. TED precisa ser do órgão da UG | *leave-one-out*: A1 224/224, A2 30/30, D 2/2, C 137/140 |
| 3 similaridade | texto da NE x objeto dos planos do órgão (TF-IDF, score ≥ 0,3 e margem ≥ 0,1) | 72/73 na calibração |
| descarte | número que não é TED do MIR; vínculo que contradiz o crédito da célula (só derruba similaridade, ou crédito exclusivo de outro TED numerado) | 1 conflito em todas as células explicadas pelo crédito |
| 4 crédito da UG | G1: todo o destaque oficial da célula (ano, órgão, PTRES, fonte) veio de um único instrumento; G1b: idem, descontado o que esse instrumento repassou a outro órgão (repasse atribuído pela G3), ex.: Palmares 2025, TED 966942; G2: o empenho sem TED é o saldo exato do crédito de um TED; G3: a célula não recebeu NC do MIR, e um instrumento do mesmo ano/PTRES/fonte foi para outro órgão, que repassou (crédito menos o que executou) exatamente o destaque da célula; G4/G5: célula com 2+ instrumentos e crédito cobrindo o destaque; saldo de cada instrumento = crédito menos o que as NEs identificadas consumiram; NE com valor igual ao saldo de um único instrumento, ou subconjunto de 2-3 NEs cuja soma é o saldo de um instrumento quando é a única combinação que casa (G5); depois, por exclusão, se só um ainda tem saldo (G4); e, se o pendente é exatamente o saldo somado de 2-3 instrumentos, eles viram um instrumento mesclado ("A + B"). Roda de novo depois da camada 5 | G1 concordou 115/115 onde o TED do texto é real; G3 concordou com a regra S nas 4 NEs que as duas cobrem; G4/G5 *leave-one-out*: exato 36/36, exclusão 3/3 |
| 5 tedinho / subdescentralização | T: NC do MIR citada no texto, com ano (2025NC000307) ou sem (NC000307 / 233518); se cancelada, vai para a relançada. S: NC citada de outro órgão (ENAP, Palmares) com um único TED com o MIR no ano + PTRES (desempate pela fonte). R: NC citada de um intermediário; saldo de cada instrumento dele (crédito menos o que executou e o já atribuído); casamento exato do valor da NE com um saldo, depois do grupo de NEs que citam a mesma NC do intermediário, e por fim por exclusão. Ex.: ENAP → UnB 2023 e 2025 | — |

Nada é rateado: o que nenhuma regra resolve fica em "não identificado", no grão da
UG.

`similar_celula.py` testa uma variação da similaridade: compara a NE só com o
objeto dos instrumentos que mandaram crédito para a célula dela, usando também os
objetos da página do gov.br. Na calibração acertou 37 de 37 (score ≥ 0,1 e margem
≥ 0,05), mas resolve só 2 NEs das restantes (R$ 180 mil). Ainda não entra no
pipeline.

## O que falta (R$ 23.769,36)

São 9 NEs, todas no PTRES 233518, fonte OQ, ligadas ao crédito que a ENAP recebeu
por tedinho: a própria ENAP (R$ 6.311,56, cita a NC000496, que não é do MIR) e
repasses da ENAP a IBGE, UTFPR, UFRB, IFBaiano, UFRJ e UFPR (R$ 1.196,38 a R$
3.549,56). O saldo da ENAP nessas fontes é muito maior que o pendente e está em três
ou mais processos, então nenhum casamento fecha.

## Como rodar

Entradas que não ficam no git:

- CSVs do Tesouro Gerencial na raiz do repositório (ou na pasta de `TED_CSV_DIR`):
  - `Execução TED por UG - 2023_24_25 e 26.csv` (consulta oficial do MIR);
  - `ppa_tesouro(2023).csv` … `ppa_tesouro(2026).csv`: relatório "Notas de empenhos
    por programa PPA (EM REAIS)", métrica "Movim. Líquido - R$", RP 2 e 6,
    UO 67101, sem filtro de saldo;
  - `2023.csv` … `2026.csv`: o relatório antigo, usado só para listar as UGs.
- `dados/`: tabelas do data warehouse e páginas do gov.br, regeneradas pelos
  scripts abaixo.

```bash
./exportar_dados.sh            # tabelas do DW (padrão: container mir-dump-pg17, banco analytics)
python3 baixar_govbr.py        # páginas de transferências do MIR no gov.br
python3 pipeline.py            # execução por instrumento; saídas em saida/
python3 similar_celula.py      # opcional: similaridade restrita à célula
```

Saídas em `saida/`:

- `execucao_por_ted.csv`: ano × instrumento, com empenhado, liquidado, pago, tipo
  (TED ou tedinho), parceiro, objeto e a parte do empenhado que veio de cada camada;
- `execucao_por_ne.csv`: cada linha de NE com o instrumento e a regra que o identificou;
- `ne_nao_identificadas.csv`: uma linha por NE ainda sem instrumento.

## Limitações

- 2026 vai até 30/09/2026, a posição da consulta oficial usada. Para incluir
  outubro, as duas consultas precisam ser reextraídas na mesma data.
- O vínculo da cascata vem do dump local de 10/09/2026. NEs posteriores passam
  só pelas regras novas.
- A camada de similaridade é estatística. Convém mantê-la marcada à parte no
  produto final.
