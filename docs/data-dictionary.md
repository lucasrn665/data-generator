# Dicionário de dados

Este catálogo é derivado dos schemas PyArrow em `domain/schemas.py`, dos
modelos/enums, validadores e manifesto. Os CSVs são a representação física; os
tipos abaixo são os tipos canônicos.

O contrato de streaming está documentado em
[event-hubs-contract.md](event-hubs-contract.md).

## Convenções

- `string`, `date32`, `timestamp[us, tz=UTC]`, `decimal128(18,2)`, `decimal128(5,2)`,
  `bool` e `int64` correspondem, respectivamente, a `STRING`, `DATE`,
  `TIMESTAMP` (interpretado em UTC), `DECIMAL(18,2)`, `DECIMAL(5,2)`, `BOOLEAN`
  e `BIGINT` no Databricks/Spark.
- Campos obrigatórios são `nullable=false`; somente campos explicitamente
  opcionais aceitam nulo.
- Valores monetários permanecem `Decimal`, com exatamente duas casas. CSV não
  possui tipo físico; o consumidor deve aplicar o schema canônico.
- `event_at` é a ocorrência econômica, `effective_at` é o instante usado na
  contabilidade e `ingested_at` é a chegada à plataforma. Timestamps são UTC e
  serializados com `Z`.
- Exemplos são inteiramente sintéticos e não representam credenciais ou dados
  reais.

## `customers.csv`

Finalidade: dimensão de clientes sintéticos. Granularidade: uma linha por
cliente. Chave primária: `customer_id` (`SYN-CUS-*`).

| Coluna | PyArrow | Spark | Nulo | Descrição / valores | FK |
|---|---|---|---|---|---|
| customer_id | string | STRING | não | Identificador sintético | — |
| synthetic_name | string | STRING | não | Nome Faker sintético | — |
| birth_date | date32 | DATE | não | Data de nascimento sintética | — |
| synthetic_email | string | STRING | não | E-mail sintético | — |
| created_date | date32 | DATE | não | Data de criação | — |
| activity_profile | string | STRING | não | `low`, `medium`, `high` | — |
| status | string | STRING | não | `active`, `inactive` | — |

Exemplo: `SYN-CUS-000000000001,Cliente Sintético 01,1990-01-01,cliente01@example.invalid,2025-01-01,medium,active`.

## `addresses.csv`

Finalidade: endereço sintético. Granularidade: um endereço por cliente nesta
versão, exatamente um marcado como principal. Chave primária: `address_id`
(`SYN-ADR-*`). FK: `customer_id` → `customers.customer_id`.

| Coluna | PyArrow | Spark | Nulo | Descrição / valores | FK |
|---|---|---|---|---|---|
| address_id | string | STRING | não | Identificador sintético | — |
| customer_id | string | STRING | não | Cliente proprietário | customers |
| street | string | STRING | não | Logradouro sintético | — |
| number | string | STRING | não | Número sintético | — |
| complement | string | STRING | sim | Complemento opcional | — |
| neighborhood | string | STRING | não | Bairro sintético | — |
| city | string | STRING | não | Cidade sintética | — |
| state | string | STRING | não | Estado sintético | — |
| synthetic_postal_code | string | STRING | não | Código postal sintético | — |
| country | string | STRING | não | País sintético | — |
| is_primary | bool | BOOLEAN | não | Indicador do principal | — |

Exemplo: `SYN-ADR-000000000001,SYN-CUS-000000000001,Rua Sintética,10,,Centro,Cidade Sintética,SP,SYN-00000-000,BR,true`.

## `accounts.csv`

Finalidade: contas e seus saldos de abertura. Granularidade: uma linha por
conta. Chave primária: `account_id` (`SYN-ACC-*`). FK: `customer_id` →
`customers.customer_id`.

| Coluna | PyArrow | Spark | Nulo | Descrição / valores | FK |
|---|---|---|---|---|---|
| account_id | string | STRING | não | Identificador sintético | — |
| customer_id | string | STRING | não | Cliente da conta | customers |
| account_type | string | STRING | não | `checking` ou `savings` | — |
| currency | string | STRING | não | Moeda configurada, atualmente `BRL` | — |
| opening_balance | decimal128(18,2) | DECIMAL(18,2) | não | Saldo de abertura; `Decimal` | — |
| opened_date | date32 | DATE | não | Data de abertura | — |
| status | string | STRING | não | `active` ou `inactive` | — |

Exemplo: `SYN-ACC-000000000001,SYN-CUS-000000000001,checking,BRL,1250.00,2025-01-01,active`.

## `cards.csv`

Finalidade: cartões exclusivamente de débito. Granularidade: cartão por
conta. Chave primária: `card_id` (`SYN-CRD-*`). FK: `account_id` →
`accounts.account_id`.

| Coluna | PyArrow | Spark | Nulo | Descrição / valores | FK |
|---|---|---|---|---|---|
| card_id | string | STRING | não | Identificador sintético, não é PAN | — |
| account_id | string | STRING | não | Conta vinculada | accounts |
| card_type | string | STRING | não | Somente `debit` | — |
| status | string | STRING | não | `active` ou `blocked` | — |
| issued_date | date32 | DATE | não | Emissão | — |
| expiration_date | date32 | DATE | não | Posterior à emissão | — |
| daily_purchase_limit | decimal128(18,2) | DECIMAL(18,2) | não | Limite diário positivo | — |
| currency | string | STRING | não | Moeda da conta | — |

Exemplo: `SYN-CRD-000000000001,SYN-ACC-000000000001,debit,active,2025-01-01,2030-01-01,500.00,BRL`.

## `merchants.csv`

Finalidade: estabelecimentos sintéticos. Granularidade: um estabelecimento.
Chave primária: `merchant_id` (`SYN-MER-*`).

| Coluna | PyArrow | Spark | Nulo | Descrição / valores | FK |
|---|---|---|---|---|---|
| merchant_id | string | STRING | não | Identificador sintético | — |
| synthetic_name | string | STRING | não | Nome sintético | — |
| category | string | STRING | não | `grocery`, `restaurant`, `pharmacy`, `fuel`, `retail` | — |
| category_code | string | STRING | não | Código `SYN-MCC-*` coerente | — |
| city | string | STRING | não | Cidade sintética | — |
| state | string | STRING | não | Estado sintético | — |
| country | string | STRING | não | País sintético | — |
| risk_profile | string | STRING | não | `low`, `medium`, `high` | — |
| created_date | date32 | DATE | não | Data de criação | — |
| status | string | STRING | não | `active` ou `inactive` | — |

Exemplo: `SYN-MER-000000000001,Comércio Sintético,grocery,SYN-MCC-GROCERY,Cidade Sintética,SP,BR,low,2025-01-01,active`.

## `transactions.csv`

Finalidade: tentativas de compra e eventos de estorno. Granularidade: um
evento de transação. Chave primária: `transaction_id` (`SYN-TXN-*`). FKs:
`account_id` → contas, `card_id` → cartões, `merchant_id` → estabelecimentos,
`original_transaction_id` → `transaction_id` (somente estornos).

| Coluna | PyArrow | Spark | Nulo | Descrição / valores | FK |
|---|---|---|---|---|---|
| transaction_id | string | STRING | não | ID sintético do evento | — |
| account_id | string | STRING | não | Conta usada | accounts |
| card_id | string | STRING | não | Cartão usado | cards |
| merchant_id | string | STRING | não | Estabelecimento | merchants |
| transaction_type | string | STRING | não | `card_purchase`, `card_purchase_reversal` | — |
| status | string | STRING | não | Compra: `approved`/`declined`; estorno: `completed` | — |
| amount | decimal128(18,2) | DECIMAL(18,2) | não | Valor positivo | — |
| currency | string | STRING | não | Moeda configurada | — |
| effective_at | timestamp[us, tz=UTC] | TIMESTAMP | não | Instante contábil | — |
| event_at | timestamp[us, tz=UTC] | TIMESTAMP | não | Ocorrência econômica | — |
| ingested_at | timestamp[us, tz=UTC] | TIMESTAMP | não | Chegada; ≥ `event_at` | — |
| decline_reason | string | STRING | sim | Motivos fechados de recusa | — |
| original_transaction_id | string | STRING | sim | Nulo em compras; obrigatório em estornos | transactions |

Exemplo: `SYN-TXN-000000000001,SYN-ACC-000000000001,SYN-CRD-000000000001,SYN-MER-000000000001,card_purchase,approved,25.00,BRL,2025-12-31T12:00:00.000000Z,2025-12-31T12:00:00.000000Z,2025-12-31T12:00:05.000000Z,,`.

## `transaction_labels.csv`

Finalidade: ground truth separado de fraude sintética. Granularidade: um rótulo
por tentativa original, nunca por estorno. Chave primária/FK: `transaction_id`
→ `transactions.transaction_id`.

| Coluna | PyArrow | Spark | Nulo | Descrição / valores | FK |
|---|---|---|---|---|---|
| transaction_id | string | STRING | não | Tentativa rotulada | transactions |
| is_synthetic_fraud | bool | BOOLEAN | não | Classificação artificial | — |
| risk_pattern | string | STRING | sim | Nulo no normal; `high_amount`, `rapid_velocity`, `new_account_burst` | — |
| risk_score | decimal128(5,2) | DECIMAL(5,2) | não | `0.00` normal; score determinístico 85/90/95 | — |
| label_version | string | STRING | não | Versão centralizada (`1.0.0`) | — |

Exemplo: `SYN-TXN-000000000001,false,,0.00,1.0.0`.

## `transfers.csv`

Finalidade: tentativas de transferência interna. Granularidade: uma tentativa.
Chave primária: `transfer_id` (`SYN-TRF-*`). FKs: origem e destino →
`accounts.account_id`.

| Coluna | PyArrow | Spark | Nulo | Descrição / valores | FK |
|---|---|---|---|---|---|
| transfer_id | string | STRING | não | ID sintético | — |
| source_account_id | string | STRING | não | Origem, diferente do destino | accounts |
| destination_account_id | string | STRING | não | Destino | accounts |
| transfer_type | string | STRING | não | `internal_transfer` | — |
| status | string | STRING | não | `completed` ou `declined` | — |
| amount | decimal128(18,2) | DECIMAL(18,2) | não | Valor positivo | — |
| currency | string | STRING | não | Moeda configurada | — |
| effective_at | timestamp[us, tz=UTC] | TIMESTAMP | não | Instante contábil | — |
| event_at | timestamp[us, tz=UTC] | TIMESTAMP | não | Ocorrência econômica | — |
| ingested_at | timestamp[us, tz=UTC] | TIMESTAMP | não | Chegada | — |
| decline_reason | string | STRING | sim | `insufficient_funds` ou `synthetic_risk_rule` | — |

Exemplo: `SYN-TRF-000000000001,SYN-ACC-000000000001,SYN-ACC-000000000002,internal_transfer,completed,10.00,BRL,2025-12-31T13:00:00.000000Z,2025-12-31T13:00:00.000000Z,2025-12-31T13:00:05.000000Z,`.

## `ledger_entries.csv`

Finalidade: subledger imutável das contas. Granularidade: um lançamento.
Chave primária: `entry_id` (`SYN-ENT-*`). FK: `account_id` → contas e
`reference_id` → entidade do lançamento.

| Coluna | PyArrow | Spark | Nulo | Descrição / valores | FK |
|---|---|---|---|---|---|
| entry_id | string | STRING | não | ID sintético | — |
| account_id | string | STRING | não | Conta afetada | accounts |
| entry_type | string | STRING | não | `opening_balance`, `card_purchase`, `card_purchase_reversal`, `internal_transfer_debit`, `internal_transfer_credit` | — |
| direction | string | STRING | não | `credit` ou `debit` | — |
| amount | decimal128(18,2) | DECIMAL(18,2) | não | Positivo, escala 2 | — |
| currency | string | STRING | não | Moeda da conta | — |
| effective_at | timestamp[us, tz=UTC] | TIMESTAMP | não | Ordem contábil | — |
| reference_id | string | STRING | não | Abertura, transação ou transferência | entidade correspondente |
| sequence_number | int64 | BIGINT | não | Ordenação estável não negativa | — |

Exemplo: `SYN-ENT-000000000001,SYN-ACC-000000000001,opening_balance,credit,1250.00,BRL,2025-01-01T00:00:00.000000Z,SYN-REF-OPEN-000000000001,0`.

## Schema canônico, observado e qualidade

O schema canônico é o definido no código e usado na validação do cenário
`valid`. O schema observado é o que um consumidor encontra no CSV de um
cenário: `late_event` só muda horários/ordem, enquanto cenários de qualidade
podem adicionar, remover, renomear coluna, introduzir nulo/FK órfã, duplicar
linhas ou inserir valores incompatíveis. O schema canônico não é flexibilizado.

Mutações de qualidade são aplicadas após geração, validação financeira e
reconciliação; ledger, transferências e labels não são alvos dos cenários
iniciais. O manifesto registra o cenário e seus agregados sem expor registros.

O saldo é sempre `soma(créditos) - soma(débitos)`. Aberturas são créditos;
compras aprovadas são débitos; estornos integrais são créditos; transferências
concluídas são um débito na origem e um crédito no destino. Recusas não geram
lançamentos. A reconciliação exige saldo não negativo e correspondência exata
entre eventos e lançamentos.

### Matriz de cenários inválidos

| Cenário | Alvo | Violação esperada |
|---|---|---|
| duplicate_exact | clientes, endereços, contas, cartões, estabelecimentos ou transações | chave primária repetida com conteúdo idêntico |
| duplicate_conflicting | campos descritivos autorizados | chave repetida com atributo sintético conflitante |
| required_null | campo descritivo obrigatório autorizado | obrigatoriedade/nullability |
| orphan_foreign_key | FKs autorizadas | referência a pai inexistente (`SYN-MISSING-*`) |
| late_event | transações | atraso de ingestão intencional acima do limite |
| schema_additive_column | transações | coluna observada adicional |
| schema_missing_column | transações | `merchant_id` ausente |
| schema_renamed_column | transações | `merchant_id` renomeado |
| schema_incompatible_value | transações | valor textual incompatível com DECIMAL |
| schema_unknown_enum | transações | status fora do enum permitido |
