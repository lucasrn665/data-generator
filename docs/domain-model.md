# Modelo de domínio

Este documento delimita o modelo do gerador. Clientes, endereços, contas,
cartões de débito, estabelecimentos e o ledger de abertura estão implementados;
as demais entidades permanecem planejadas.

## Entidades previstas

- **Cliente**: pessoa inteiramente sintética, identificada por um prefixo que
  deixe explícita sua origem artificial.
- **Endereço**: endereço sintético associado a um cliente. Na primeira versão,
  cada cliente terá exatamente um endereço principal.
- **Conta**: conta sintética dos tipos `checking` ou `savings`, pertencente a
  exatamente um cliente. Seu valor monetário representa o saldo de abertura; o
  saldo é derivado exclusivamente do ledger.
- **Lançamento de ledger**: registro imutável de crédito ou débito associado a
  uma conta. Nesta etapa, existe exatamente um crédito de abertura por conta.
- **Cartão**: instrumento sintético associado diretamente a uma conta, sem PAN,
  CVV, senha, trilha ou número bancário. O tipo atual é exclusivamente `debit`.
- **Estabelecimento**: recebedor sintético, sem CNPJ ou identificador oficial.
  As categorias fechadas são `grocery`, `restaurant`, `pharmacy`, `fuel` e
  `retail`, pareadas respectivamente a códigos sintéticos `SYN-MCC-*`.
- **Transação**: tentativa de movimentação financeira, aprovada ou recusada.
- **Transferência**: movimentação consistente entre uma conta de origem e uma
  conta de destino.
- **Saldo**: posição monetária calculada, nunca atualizada por efeito colateral,
  como créditos menos débitos de uma conta.

## Relacionamentos planejados

Na primeira versão, cada cliente terá exatamente um endereço principal. O
modelo deverá permitir múltiplos endereços futuramente, mas essa cardinalidade
não será configurável agora.

Cada cliente terá entre `accounts.min_per_customer` e
`accounts.max_per_customer` contas e deverá possuir pelo menos uma. Cada conta
pertencerá a exatamente um cliente. Cada conta possui a quantidade configurada
de cartões de débito, e cada cartão pertence exatamente a uma conta. Uma conta
poderá possuir transações, transferências e saldos. Estornos deverão referenciar
uma transação anterior. Clientes, endereços e contas possuem schemas PyArrow
explícitos; os lançamentos também possuem schema explícito e são publicados em
`ledger_entries.csv`. Cartões e estabelecimentos são publicados em `cards.csv`
e `merchants.csv`. Os schemas das demais entidades serão definidos antes de
suas implementações.

Todos os identificadores e atributos deverão ser sintéticos, reproduzíveis por
seed e incapazes de representar deliberadamente pessoas ou instrumentos reais.
