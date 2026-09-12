# Modelo de domínio

Este documento delimita o modelo planejado. Nenhuma das entidades abaixo está
implementada nesta etapa.

## Entidades previstas

- **Cliente**: pessoa inteiramente sintética, identificada por um prefixo que
  deixe explícita sua origem artificial.
- **Endereço**: endereço sintético associado a um cliente.
- **Conta**: conta sintética pertencente a um cliente.
- **Cartão**: instrumento sintético associado a uma conta, sem reproduzir
  números de cartões reais.
- **Estabelecimento**: recebedor sintético de pagamentos.
- **Transação**: tentativa de movimentação financeira, aprovada ou recusada.
- **Transferência**: movimentação consistente entre uma conta de origem e uma
  conta de destino.
- **Saldo**: posição monetária derivada das movimentações válidas de uma conta.

## Relacionamentos planejados

Um cliente poderá possuir endereços e contas; uma conta poderá possuir cartões,
transações, transferências e saldos. Estornos deverão referenciar uma transação
anterior. As cardinalidades e os esquemas PyArrow serão definidos antes da
implementação de cada entidade.

Todos os identificadores e atributos deverão ser sintéticos, reproduzíveis por
seed e incapazes de representar deliberadamente pessoas ou instrumentos reais.

