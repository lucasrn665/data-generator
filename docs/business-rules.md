# Regras de negócio

As regras abaixo orientam as funcionalidades implementadas e as etapas futuras.

- Toda geração recebe uma seed e produz o mesmo resultado para os mesmos
  parâmetros e versão do gerador.
- Identificadores usam convenções que os tornam claramente sintéticos.
- Chaves estrangeiras sempre apontam para registros existentes.
- Valores monetários são calculados com `Decimal`, nunca com `float`.
- Cada cliente possui exatamente um endereço principal na primeira versão.
  Múltiplos endereços serão permitidos futuramente, sem configuração nesta
  versão.
- Cada cliente possui entre `accounts.min_per_customer` e
  `accounts.max_per_customer` contas; o mínimo configurado deve ser pelo menos
  um.
- Cada conta pertence a exatamente um cliente e possui o tipo `checking` ou
  `savings`.
- O valor monetário da conta gerada é seu saldo de abertura. Cada conta recebe
  exatamente um lançamento de abertura positivo, em crédito e na mesma moeda.
- O ledger atual é apenas o subledger das contas dos clientes. O crédito de
  abertura não possui contrapartida em uma conta contábil nesta etapa; não há
  plano de contas nem razão geral do banco.
- O instante efetivo da abertura é `00:00:00 UTC` na `opened_date` da conta,
  data que já é derivada deterministicamente de `reference_date`.
- Saldos são sempre calculados como créditos menos débitos, sem estado mutável,
  e devem reconciliar exatamente com o saldo de abertura. Transferências
  futuras deverão gerar efeitos equivalentes e opostos entre contas.
- Contas não podem possuir saldo negativo e, inicialmente, não haverá cheque
  especial.
- Transações recusadas não alteram saldos.
- Cada transação aprovada pode receber no máximo um estorno, que deve referenciar
  a transação original, ser integral e compensar seu efeito.
- Transferências geram efeitos equivalentes e opostos na origem e no destino.
- Saldos são reconciliáveis com as movimentações aprovadas.
- O diretório padrão de saída é `data/output`. Caminhos relativos são resolvidos
  a partir da raiz do projeto.
- Arquivos gerados ficam fora de `src/` e fora do versionamento Git, embora
  possam ficar dentro do repositório. `data/output/` deve permanecer no
  `.gitignore`.
- A exportação rejeita caminhos absolutos, escapes da raiz do projeto e
  diretórios de saída localizados dentro de `src/` ou `.git/`.
- Uma execução válida é publicada atomicamente como um diretório contendo três
  CSVs e `manifest.json`. O manifesto registra versões, parâmetros, contagens,
  tamanhos e checksums SHA-256 sem dados pessoais ou valores variáveis no tempo.
- Reexecuções idênticas validam e reutilizam a publicação existente. Conjuntos
  ausentes, inválidos ou divergentes não são sobrescritos.
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
  aprovadas que serão estornadas. A taxa não se aplica a transações recusadas.
- `late_event_rate_overall` é a proporção de todos os eventos entregues com
  atraso. A entrega tardia é independente da classificação de fraude e do
  status da transação.

Cada regra deverá receber testes automatizados quando a funcionalidade
correspondente for implementada.
