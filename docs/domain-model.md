# Modelo de domínio

Este documento delimita o modelo do gerador. Clientes, endereços e contas estão
implementados; as demais entidades permanecem planejadas.

## Entidades previstas

- **Cliente**: pessoa inteiramente sintética, identificada por um prefixo que
  deixe explícita sua origem artificial.
- **Endereço**: endereço sintético associado a um cliente. Na primeira versão,
  cada cliente terá exatamente um endereço principal.
- **Conta**: conta sintética dos tipos `checking` ou `savings`, pertencente a
  exatamente um cliente. Seu valor monetário representa o saldo de abertura; o
  saldo atual será derivado do ledger em uma etapa posterior.
- **Cartão**: instrumento sintético associado a uma conta, sem reproduzir
  números de cartões reais. A primeira versão terá somente cartões de débito;
  cartões de crédito pertencem ao roadmap futuro.
- **Estabelecimento**: recebedor sintético de pagamentos.
- **Transação**: tentativa de movimentação financeira, aprovada ou recusada.
- **Transferência**: movimentação consistente entre uma conta de origem e uma
  conta de destino.
- **Saldo**: posição monetária derivada das movimentações válidas de uma conta.

## Relacionamentos planejados

Na primeira versão, cada cliente terá exatamente um endereço principal. O
modelo deverá permitir múltiplos endereços futuramente, mas essa cardinalidade
não será configurável agora.

Cada cliente terá entre `accounts.min_per_customer` e
`accounts.max_per_customer` contas e deverá possuir pelo menos uma. Cada conta
pertencerá a exatamente um cliente. Uma conta poderá possuir cartões,
transações, transferências e saldos. Estornos deverão referenciar uma transação
anterior. Clientes, endereços e contas possuem schemas PyArrow explícitos; os
schemas das demais entidades serão definidos antes de suas implementações.

Todos os identificadores e atributos deverão ser sintéticos, reproduzíveis por
seed e incapazes de representar deliberadamente pessoas ou instrumentos reais.
