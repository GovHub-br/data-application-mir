# Ingestão via e-mail — filtro por intervalo de datas

As DAGs de ingestão via e-mail do Tesouro Gerencial filtram os e-mails por
data. Todas aceitam dois parâmetros **opcionais** ao disparar manualmente
(`Trigger DAG w/ config`):

| Parâmetro      | Formato      | Descrição                                            |
| -------------- | ------------ | ---------------------------------------------------- |
| `data_inicial` | `YYYY-MM-DD` | Data inicial do intervalo, **inclusive**.            |
| `data_final`   | `YYYY-MM-DD` | Data final do intervalo, **inclusive**.              |

A lógica compartilhada vive em
[`cliente_email.py`](../../../../plugins/cliente_email.py)
(`resolve_email_date_range`, `build_date_criteria`) e os parâmetros em
[`email_ingest_params.py`](../../../../plugins/email_ingest_params.py)
(`date_range_params`). Toda DAG de e-mail reutiliza essa infraestrutura.

## Comportamento

O intervalo é **inclusivo nas duas pontas**. Internamente traduzimos para a
semântica do IMAP (`SINCE` é inclusivo; `BEFORE` é exclusivo), somando 1 dia
ao `data_final` para que o próprio dia final entre no resultado.

| `data_inicial` | `data_final` | Resultado                                                            |
| -------------- | ------------ | ------------------------------------------------------------------- |
| vazio          | vazio        | **Apenas o dia atual** (comportamento padrão — inalterado).          |
| `2026-08-30`   | `2026-08-30` | Somente 30/08/2026.                                                  |
| `2026-08-01`   | `2026-08-31` | Todos os dias de 01/08 a 31/08 (inclusive).                         |
| `2026-08-01`   | vazio        | De 01/08 até a data atual da execução (inclusive).                  |
| vazio          | `2026-08-31` | Todos os e-mails até 31/08 (inclusive).                             |

O "dia atual" usa sempre o timezone do projeto (`America/Sao_Paulo`).

## Ordenação

Os anexos são processados em **ordem cronológica, do mais antigo para o mais
recente**, usando a data/hora efetiva de cada mensagem (`msg.date`) — não a
ordem em que o servidor IMAP os devolve. Mensagens no mesmo dia mantêm a
ordem por horário.

## Validação

- Datas fora do formato `YYYY-MM-DD` (ex.: `30/08/2026`) falham com mensagem
  clara antes de qualquer chamada ao IMAP.
- `data_inicial` posterior a `data_final` é rejeitado explicitamente.

## Exemplos de disparo (Trigger DAG w/ config)

Um único dia:

```json
{ "data_inicial": "2026-08-30", "data_final": "2026-08-30" }
```

Intervalo (backfill):

```json
{ "data_inicial": "2026-08-01", "data_final": "2026-08-31" }
```

A partir de uma data até a execução:

```json
{ "data_inicial": "2026-08-01", "data_final": null }
```

Sem configuração → busca apenas o dia atual (agendamento normal).

## DAGs que usam este filtro

- `email_tesouro_ppa_ingest_dag` (referência)
- `email_tesouro_teds_notas_empenhadas_ingest_dag`
- `email_tesouro_emendas_ingest`
- `email_programacoes_financeiras_mir_ingest`
- `email_programacao_acao_por_PTRES_ingest`
- `email_notas_credito_ingest_mir_pos_2026`
- `email_notas_credito_ingest_mir_ate_2025` (aplica o intervalo às duas caixas:
  notas enviadas e recebidas)

> **Nota sobre backfills grandes:** as DAGs baseadas em
> `fetch_and_process_email` (emendas, PFs, notas de crédito, programação por
> PTRES) concatenam os CSVs de todos os e-mails do intervalo em um único
> resultado antes de inserir. Para janelas muito largas, prefira dividir o
> backfill em intervalos menores. As DAGs que ingerem anexo a anexo
> (`email_tesouro_ppa_ingest_dag`, `email_tesouro_teds_notas_empenhadas_ingest_dag`)
> processam e liberam cada ZIP individualmente.
