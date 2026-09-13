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
- Cada conta possui `cards.per_account` cartões, exclusivamente do tipo `debit`.
  Cartões referenciam contas, usam `Decimal` no limite diário e não contêm PAN,
  CVV, senha, trilha magnética ou número bancário.
- A quantidade bloqueada é a taxa configurada aplicada ao total e arredondada
  deterministicamente para o inteiro mais próximo com `ROUND_HALF_UP`.
- Estabelecimentos não possuem CNPJ. Categoria e código obedecem ao conjunto
  fechado documentado no modelo de domínio, usando códigos `SYN-MCC-*`.
- O valor monetário da conta gerada é seu saldo de abertura. Cada conta recebe
  exatamente um lançamento de abertura positivo, em crédito e na mesma moeda.
- O ledger atual é apenas o subledger das contas dos clientes. O crédito de
  abertura não possui contrapartida em uma conta contábil nesta etapa; não há
  plano de contas nem razão geral do banco.
- O instante efetivo da abertura é `00:00:00 UTC` na `opened_date` da conta,
  data que já é derivada deterministicamente de `reference_date`.
- Saldos são sempre calculados como créditos menos débitos, sem estado mutável,
  e devem reconciliar exatamente com todo o ledger.
- Contas não podem possuir saldo negativo e, inicialmente, não haverá cheque
  especial.
- Tentativas de compra são ordenadas por `effective_at` e ID. Aprovações exigem
  cartão e estabelecimento ativos, saldo e limite diário suficientes, e geram
  exatamente um débito. Recusas não alteram saldo nem consomem limite diário.
- A meta de recusas usa `ROUND_HALF_UP`. A regra sintética preenche a meta apenas
  quando a tentativa seria válida; restrições legítimas podem elevar o total
  real e são contabilizadas como recusas adicionais.
- `event_at` representa a ocorrência econômica e coincide com `effective_at`;
  `ingested_at` representa a chegada. Regras financeiras usam o instante
  econômico, nunca a chegada.
- No conjunto canônico, o atraso operacional fica no intervalo configurado e
  não supera o limite tardio. `late_event` altera somente `ingested_at`, com
  atraso estritamente superior ao limite, e ordena a tabela por chegada.
- Cada compra aprovada pode receber no máximo um estorno concluído, selecionado
  por seed própria e cota `ROUND_HALF_UP`. O estorno é integral, referencia a
  compra imutável, gera um crédito e recompõe saldo e consumo no dia da compra.
- `transactions.count` conta somente tentativas de compra. Estornos são eventos
  adicionais: total de eventos é tentativas mais estornos.
- A meta de fraude sintética é `transactions.count × fraud_rate_overall`, com
  `ROUND_HALF_UP`, e aplica-se somente às compras originais, independentemente
  do status. Cada tentativa recebe exatamente um rótulo em arquivo separado.
- `high_amount` usa o máximo monetário configurado; `rapid_velocity` agrupa
  tentativas no mesmo cartão em até cinco minutos; `new_account_burst` concentra
  tentativas, na data de referência, na conta mais recentemente aberta no
  conjunto sintético. Cada tentativa do agrupamento selecionada pela cota recebe
  seu próprio rótulo.
- O `risk_score` é `Decimal` entre `0.00` e `100.00`: normal usa `0.00` e os
  padrões usam respectivamente `95.00`, `90.00` e `85.00`. O rótulo não cria
  efeitos contábeis; compras alteradas pelos padrões são reavaliadas pelas regras
  financeiras antes da criação de qualquer lançamento.
- Tentativas de transferência usam uma seed própria e são ordenadas depois dos
  eventos de cartão. A cota de recusas usa `ROUND_HALF_UP`; restrições de saldo
  podem produzir recusas adicionais.
- Transferências concluídas geram atomicamente um débito na origem e um crédito
  no destino, com mesmo valor, moeda, referência e instante. Recusas não geram
  lançamentos. Nenhum saldo intermediário pode ficar negativo.
- Débitos e créditos de transferência devem ser iguais, portanto seu efeito no
  saldo agregado das contas do banco fictício é sempre zero.
- Saldos são reconciliáveis com as movimentações aprovadas.
- O diretório padrão de saída é `data/output`. Caminhos relativos são resolvidos
  a partir da raiz do projeto.
- Arquivos gerados ficam fora de `src/` e fora do versionamento Git, embora
  possam ficar dentro do repositório. `data/output/` deve permanecer no
  `.gitignore`.
- A exportação rejeita caminhos absolutos, escapes da raiz do projeto e
  diretórios de saída localizados dentro de `src/` ou `.git/`.
- Uma execução válida é publicada atomicamente como um diretório contendo nove
  CSVs e `manifest.json`. O manifesto registra versões, parâmetros, contagens,
  tamanhos e checksums SHA-256 sem dados pessoais ou valores variáveis no tempo.
- O caminho inclui a versão do schema batch. O manifesto registra agregados
  contábeis, incluindo totais monetários como strings com duas casas decimais.
- Reexecuções idênticas validam e reutilizam a publicação existente. Conjuntos
  ausentes, inválidos ou divergentes não são sobrescritos.
- Cenários de qualidade são derivados somente depois da validação e
  reconciliação do conjunto canônico. Um cenário por execução altera apenas a
  tabela alvo; os demais CSVs permanecem byte a byte iguais ao cenário válido.
- Duplicatas, nulos obrigatórios e FKs órfãs usam alvos fechados e nunca alteram
  valores monetários, ledger, transferências ou rótulos de fraude.
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
