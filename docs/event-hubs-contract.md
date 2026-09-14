# Contrato de eventos do Azure Event Hubs

Este documento descreve exatamente os envelopes produzidos por
`events.py` e enviados por `export/event_hubs.py`. A versão atual do evento é
`event_schema_version = "1.0.0"`, centralizada em `version.py`.

## Envelope JSON

Cada mensagem é UTF-8, termina com quebra de linha e usa JSON compacto com as
chaves na ordem abaixo:

| Campo | Tipo JSON | Obrigatório | Descrição |
|---|---|---|---|
| `event_id` | string | sim | ID sintético da transação ou transferência; é globalmente único no conjunto. |
| `event_schema_version` | string | sim | Atualmente `1.0.0`. |
| `event_type` | string | sim | `card_purchase`, `card_purchase_reversal` ou `internal_transfer`. |
| `event_at` | string | sim | Ocorrência econômica, ISO 8601 UTC terminada em `Z`. |
| `ingested_at` | string | sim | Chegada à plataforma, ISO 8601 UTC terminada em `Z`. |
| `sequence_number` | integer | sim | Começa em zero e segue a ordem de replay. |
| `partition_key` | string | sim | Chave usada para preservar ordenação por conta. |
| `reference_date` | string | sim | Data de referência da execução (`YYYY-MM-DD`). |
| `seed` | integer | sim | Seed da execução. |
| `scenario` | string | sim | Cenário selecionado na execução. |
| `payload` | object | sim | Conteúdo específico do tipo de evento. |

Valores monetários no payload são strings decimais com duas casas, nunca
números JSON. Timestamps são strings UTC com `Z`; `effective_at` existe nos
CSVs, mas não está no envelope atual.

## Payloads

### Compra e estorno

`card_purchase` e `card_purchase_reversal` usam os campos:

| Campo | Tipo | Nulo | Observação |
|---|---|---|---|
| `account_id` | string | não | Conta da operação. |
| `card_id` | string | não | Cartão sintético associado à conta. |
| `merchant_id` | string | não | Estabelecimento sintético. |
| `status` | string | não | Compra: `approved` ou `declined`; estorno: `completed`. |
| `amount` | string decimal | não | Valor positivo com escala 2. |
| `currency` | string | não | Moeda configurada, atualmente `BRL`. |
| `decline_reason` | string | sim | Nulo em aprovações/estornos; em recusas: `card_blocked`, `insufficient_funds`, `daily_limit_exceeded`, `merchant_inactive` ou `synthetic_risk_rule`. |
| `original_transaction_id` | string | sim | Nulo na compra; obrigatório no estorno e aponta para a compra aprovada. |

### Transferência

`internal_transfer` usa:

| Campo | Tipo | Nulo | Observação |
|---|---|---|---|
| `source_account_id` | string | não | Conta de origem. |
| `destination_account_id` | string | não | Conta de destino, diferente da origem. |
| `status` | string | não | `completed` ou `declined`. |
| `amount` | string decimal | não | Valor positivo com escala 2. |
| `currency` | string | não | Moeda coerente entre as contas. |
| `decline_reason` | string | sim | Nulo em conclusões; em recusas: `insufficient_funds` ou `synthetic_risk_rule`. |

## Ordenação, partições e batching

O replay ordena mensagens por `ingested_at`, depois `event_at`, `event_type` e
`event_id`. `sequence_number` é atribuído após essa ordenação. Compras,
estornos e transferências usam `account_id` ou `source_account_id` como
`partition_key`. Transferências envolvem duas contas; a decisão atual é usar a
conta de origem, mantendo a sequência do evento lógico em uma única partição.

O produtor cria lotes por chave de partição e respeita `max_batch_size`. O
limite opcional `events_per_second` controla a velocidade; zero significa sem
espera. O SDK pode repetir chamadas transitórias. A entrega é **at-least-once**,
não exactly-once: consumidores devem deduplicar por `event_id`.

No cenário `late_event`, `event_at` não muda e `ingested_at` recebe atraso
determinístico acima do limite; o replay segue a ordem de chegada, de modo que
eventos economicamente antigos podem chegar depois. Cenários com CSV
propositalmente inválido continuam enviando eventos derivados do conjunto
canônico validado, não das linhas corrompidas.

## O que não é enviado

Clientes, endereços, contas, cartões, estabelecimentos, `ledger_entries.csv` e
`transaction_labels.csv` não são publicados no Event Hubs. O ground truth de
fraude deve ser lido do ADLS e relacionado por `transaction_id`/`event_id`.

## Schema equivalente para Spark/Databricks

Uma leitura inicial pode declarar:

```text
event_id STRING NOT NULL,
event_schema_version STRING NOT NULL,
event_type STRING NOT NULL,
event_at TIMESTAMP NOT NULL,       -- interpretar em UTC
ingested_at TIMESTAMP NOT NULL,    -- interpretar em UTC
sequence_number BIGINT NOT NULL,
partition_key STRING NOT NULL,
reference_date DATE NOT NULL,
seed BIGINT NOT NULL,
scenario STRING NOT NULL,
payload STRUCT<
  account_id: STRING,
  card_id: STRING,
  merchant_id: STRING,
  source_account_id: STRING,
  destination_account_id: STRING,
  status: STRING,
  amount: DECIMAL(18,2),
  currency: STRING,
  decline_reason: STRING,
  original_transaction_id: STRING
>
```

Os campos não aplicáveis ao tipo ficam nulos. Alternativamente, consumidores
podem separar por `event_type` em três DataFrames e aplicar structs específicos
de compra/estorno, compra e transferência, preservando `amount` como
`DECIMAL(18,2)` e convertendo os timestamps `Z` para UTC.

## ADLS versus Event Hubs

| Informação | ADLS batch | Event Hubs |
|---|---|---|
| Clientes, endereços, contas, cartões e estabelecimentos | CSVs completos | não publicados |
| Compras, recusas e estornos | `transactions.csv` | envelopes financeiros |
| Transferências | `transfers.csv` | envelopes `internal_transfer` |
| Ledger e saldos derivados | `ledger_entries.csv` e manifesto | não publicados |
| Ground truth de fraude | `transaction_labels.csv` | não publicado; relacionar por ID |
| Manifesto, checksums e qualidade | `manifest.json` | não enviados |
| Ordenação | linhas/contrato batch | chegada (`ingested_at`) e sequência |
| Reexecução | publicação idempotente | replay at-least-once |

O Event Hubs é opcional (`enabled=false` por padrão). A CLI usa
`--publish-event-hubs` após gerar e validar o conjunto local; nenhuma integração
direta com Databricks é feita nesta etapa.
