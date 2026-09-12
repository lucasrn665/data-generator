# Regras de negócio

As regras abaixo são requisitos para etapas futuras e ainda não possuem
implementação neste esqueleto.

- Toda geração recebe uma seed e produz o mesmo resultado para os mesmos
  parâmetros e versão do gerador.
- Identificadores usam convenções que os tornam claramente sintéticos.
- Chaves estrangeiras sempre apontam para registros existentes.
- Valores monetários são calculados com `Decimal`, nunca com `float`.
- Transações recusadas não alteram saldos.
- Estornos referenciam transações anteriores elegíveis e compensam seu efeito.
- Transferências geram efeitos equivalentes e opostos na origem e no destino.
- Saldos são reconciliáveis com as movimentações aprovadas.
- Arquivos gerados são gravados fora do código-fonte.
- Configurações e dados gerados não contêm credenciais.

## Semântica das taxas de transação

As taxas configuradas em `configs/default.yaml` determinam as seguintes regras
de domínio:

- `fraud_rate_overall` é a proporção de todas as transações marcadas com um
  indicador sintético de fraude. A classificação de fraude é independente do
  status da transação; portanto, uma transação aprovada ou recusada pode receber
  esse indicador.
- `declined_rate_overall` é a proporção de todas as tentativas de transação que
  serão recusadas. Transações recusadas não alteram saldos.
- `reversal_rate_of_approved` é a proporção das transações inicialmente
  aprovadas que serão estornadas. A taxa não se aplica a transações recusadas, e
  todo estorno deve referenciar a transação original.
- `late_event_rate_overall` é a proporção de todos os eventos entregues com
  atraso. A entrega tardia é independente da classificação de fraude e do
  status da transação.

Cada regra deverá receber testes automatizados quando a funcionalidade
correspondente for implementada.
