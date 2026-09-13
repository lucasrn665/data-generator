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
- tipos, nulabilidade e precisão compatíveis com o esquema PyArrow;
- reprodução exata de uma amostra a partir da mesma seed;
- ausência de alteração de saldo por transações recusadas;
- vínculo válido entre estorno e transação original;
- igualdade entre débito e crédito de uma transferência;
- reconciliação do saldo com o histórico de movimentações;
- ausência de credenciais ou dados deliberadamente reais na saída.
- ausência de arquivos gerados dentro de `src/` ou `.git/`.
- presença dos três CSVs e do manifesto em toda execução publicada;
- correspondência entre manifesto, contagens, tamanhos e checksums SHA-256;
- rejeição de reexecuções incompatíveis ou de publicações preexistentes
  incompletas.

## Cenários controlados futuros

O gerador poderá oferecer cenários opt-in com problemas conhecidos, como valor
nulo, chave órfã ou duplicidade. Arquivos válidos e arquivos com anomalias
intencionais deverão ficar em execuções ou cenários separados. Os registros
anômalos deverão ser claramente marcados e reproduzíveis.
