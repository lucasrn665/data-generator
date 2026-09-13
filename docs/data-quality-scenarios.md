# Cenários de qualidade de dados

Esta é a lista inicial de cenários a serem detalhados e implementados em etapas
posteriores.

## Validações obrigatórias

- unicidade e formato sintético dos identificadores;
- ausência de chaves estrangeiras órfãs;
- exatamente um endereço principal por cliente na primeira versão;
- quantidade de contas por cliente dentro do intervalo configurado, com ao
  menos uma conta para cada cliente;
- vínculo de cada conta com exatamente um cliente e tipo de conta restrito a
  `checking` ou `savings`;
- cartões exclusivamente de débito, vinculados a contas existentes, sem
  credenciais bancárias e na cardinalidade configurada;
- limites diários positivos com escala 2, moeda e datas coerentes;
- categorias e códigos sintéticos de estabelecimentos coerentes;
- tipos, nulabilidade e precisão compatíveis com o esquema PyArrow;
- exatamente um crédito de abertura positivo por conta, com moeda coerente,
  referência sintética única e instante efetivo em UTC;
- saldo derivado não negativo e reconciliado com o saldo de abertura;
- reprodução exata de uma amostra a partir da mesma seed;
- ausência de alteração de saldo por transações recusadas;
- cobertura exata e exclusiva das compras originais pelo ground truth, sem
  rótulos para estornos e sem vazamento em `transactions.csv`;
- cota, versão, score, booleano e padrões sintéticos de fraude coerentes;
- evidências verificáveis de `high_amount`, `rapid_velocity` e
  `new_account_burst` antes da decisão financeira;
- uma correspondência exata entre compras aprovadas e débitos no ledger;
- motivos coerentes e obrigatórios somente para compras recusadas;
- limite diário recalculável apenas pelas compras aprovadas;
- vínculo válido entre estorno e transação original;
- no máximo um crédito integral de estorno para cada compra aprovada selecionada;
- saldo e consumo diário líquido reconciliados após estornos, nunca negativos;
- correspondência exata entre cada transferência concluída e seu par de
  lançamentos, sem lançamentos em recusas;
- igualdade dos totais debitado e creditado em transferências, saldo agregado
  conservado e ausência de saldo negativo intermediário;
- reconciliação do saldo com o histórico de movimentações;
- ausência de credenciais ou dados deliberadamente reais na saída.
- ausência de arquivos gerados dentro de `src/` ou `.git/`.
- presença dos nove CSVs e do manifesto em toda execução publicada;
- correspondência entre manifesto, contagens, tamanhos e checksums SHA-256;
- rejeição de reexecuções incompatíveis ou de publicações preexistentes
  incompletas.

## Cenários controlados implementados

O contrato de qualidade `1.0.0` oferece um cenário por execução:

- `duplicate_exact`: acrescenta cópias completas com a mesma chave primária;
- `duplicate_conflicting`: acrescenta cópias com a mesma chave e um campo
  descritivo diferente, marcado por `[CONFLITO-SINTETICO]`;
- `required_null`: anula um campo descritivo obrigatório somente na tabela de
  publicação, sem alterar o schema canônico;
- `orphan_foreign_key`: substitui uma FK autorizada por `SYN-MISSING-*`.

A seleção usa uma seed exclusiva por cenário. A quantidade é a contagem da
entidade multiplicada pela taxa e arredondada com `ROUND_HALF_UP`; não existe
mínimo implícito, portanto uma taxa positiva pode resultar em zero. Objetos e
tabelas canônicas não são mutados. Ledger, transferências e ground truth de
fraude nunca são alvos nesta versão.

Campos conflitantes autorizados são nomes sintéticos de clientes e
estabelecimentos e atributos textuais de endereço/estabelecimento. Nulos são
permitidos apenas nesses campos descritivos. FKs órfãs estão limitadas a
`addresses.customer_id`, `accounts.customer_id`, `cards.account_id` e
`transactions.merchant_id`.

Cada cenário fica em `scenario=<nome>` sob o schema `1.6.1`; o manifesto registra
contagens original/publicada, seleção, linhas adicionais, chaves duplicadas,
tipo e quantidade esperada de violações e confirmação da validação canônica.
