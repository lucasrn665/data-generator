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
- presença dos oito CSVs e do manifesto em toda execução publicada;
- correspondência entre manifesto, contagens, tamanhos e checksums SHA-256;
- rejeição de reexecuções incompatíveis ou de publicações preexistentes
  incompletas.

## Cenários controlados futuros

O gerador poderá oferecer cenários opt-in com problemas conhecidos, como valor
nulo, chave órfã ou duplicidade. Arquivos válidos e arquivos com anomalias
intencionais deverão ficar em execuções ou cenários separados. Os registros
anômalos deverão ser claramente marcados e reproduzíveis.
