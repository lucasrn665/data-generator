# Estado do projeto

## Objetivo

Construir um gerador reproduzível de dados bancários inteiramente sintéticos
para exercícios de engenharia de dados no Databricks. A primeira entrega usará
arquivos CSV; streaming pertence ao roadmap futuro.

## Decisões de domínio aprovadas

- A geração recebe uma seed e não representa pessoas, documentos, cartões ou
  contas reais.
- A moeda inicial é BRL. Valores monetários configuráveis são strings com duas
  casas decimais e são convertidos diretamente para `Decimal`.
- A primeira versão terá somente cartões de débito; cartões de crédito são
  futuros.
- Contas não admitem saldo negativo nem cheque especial inicialmente.
- Na primeira versão, cada cliente terá exatamente um endereço principal. O
  modelo permitirá múltiplos endereços futuramente, sem configuração agora.
- Cada cliente terá entre `accounts.min_per_customer` e
  `accounts.max_per_customer` contas e deverá possuir pelo menos uma. Cada conta
  pertencerá a exatamente um cliente e terá tipo `checking` ou `savings`.
- Cada transação aprovada admite no máximo um estorno, que deve ser integral.
- Transações recusadas não alteram saldos, e transferências devem conservar o
  valor entre origem e destino.
- Arquivos válidos e arquivos com anomalias intencionais ficam em execuções ou
  cenários separados.
- `data/output` é o diretório padrão. Caminhos relativos de saída são resolvidos
  a partir da raiz do projeto.
- Dados gerados devem ficar fora de `src/` e do versionamento Git, mas podem
  ficar dentro do repositório. `data/output/` já está no `.gitignore`.
- A exportação rejeita caminhos absolutos, escapes da raiz e destinos dentro de
  `src/` ou `.git/`.

Consulte o [modelo de domínio](domain-model.md), as
[regras de negócio](business-rules.md) e os
[cenários de qualidade](data-quality-scenarios.md) para os detalhes normativos.

## Etapas concluídas

- Estrutura inicial do pacote, configuração, documentação e teste de instalação.
- Contrato tipado e imutável para `configs/default.yaml`.
- Carregamento seguro com `yaml.safe_load`.
- Conversão de datas e valores monetários para `date` e `Decimal`.
- Validação de campos obrigatórios, propriedades desconhecidas, valores não
  negativos, intervalos `min <= max` e taxas entre zero e um.
- Validação de `accounts.min_per_customer` como inteiro maior ou igual a um.
- Rejeição de moeda e formato de saída não suportados.
- Modelos tipados e imutáveis de clientes, endereços e contas.
- Schemas PyArrow explícitos, com datas, nulabilidade e saldo de abertura
  `decimal128(18, 2)`.
- Geração determinística e isolada por componente, com seeds derivadas por
  SHA-256, instâncias próprias de `random.Random` e Faker `pt_BR`.
- IDs sintéticos prefixados, um endereço principal por cliente e cardinalidade
  configurada de contas com chaves estrangeiras válidas.
- Conversão explícita de clientes, endereços e contas para tabelas PyArrow.
- Serialização batch determinística de `customers.csv`, `addresses.csv`,
  `accounts.csv` e `ledger_entries.csv`.
- Resolução do diretório de saída pela raiz do projeto e rejeição de caminhos
  absolutos, travessias, escapes e destinos dentro de `src/` ou `.git/`.
- Pipeline batch para carregar, gerar, validar e exportar o conjunto atual.
- CLI com `argparse`, resumo sem registros individuais e tratamento legível dos
  erros esperados.
- Manifesto JSON determinístico com versões, parâmetros, contagens, tamanhos e
  checksums SHA-256 dos nove CSVs, além de invariantes contábeis e resumos de
  cartões e estabelecimentos.
- Publicação conjunta por diretório de staging irmão, com manifesto escrito por
  último e exposição do caminho final somente após sucesso integral.
- Reexecução idempotente mediante validação exata do manifesto e dos arquivos;
  publicações divergentes nunca são sobrescritas.
- Subledger imutável de contas com um crédito de abertura determinístico por
  conta, valores `Decimal`, referências sintéticas e timestamps UTC.
- Cálculo puro de saldos como créditos menos débitos e reconciliação com os
  saldos de abertura antes da publicação batch.
- Contrato batch `1.1.0`, gerador `0.2.0` e caminho particionado também pela
  versão do schema, preservando a coexistência com publicações anteriores.
- Exportação determinística do ledger validado e reconciliado, com valores
  monetários decimais e timestamps UTC inequívocos.
- Contrato tipado para quantidade de estabelecimentos, cartões por conta,
  intervalo de limite diário e taxa inicial de bloqueio.
- Modelos, schemas e geradores determinísticos isolados para estabelecimentos e
  cartões exclusivamente de débito, sem credenciais ou identificadores oficiais.
- Contrato batch `1.2.0`, gerador `0.3.0`, com `cards.csv` e `merchants.csv`
  integrados à publicação atômica e ao manifesto.
- Tentativas determinísticas de compra com aprovações, recusas coerentes, limite
  diário recalculável e débitos apenas para aprovações.
- Contrato batch `1.3.0`, gerador `0.4.0`, com `transactions.csv`, agregados no
  manifesto e reconciliação do saldo final pelo ledger completo.
- Estornos integrais determinísticos de compras aprovadas, como eventos
  adicionais imutáveis com um crédito correspondente e recomposição do limite.
- Contrato batch `1.4.0` e gerador `0.5.0`, mantendo compras e estornos no mesmo
  `transactions.csv` e seus efeitos no ledger publicado.
- Contrato tipado de transferências internas, geração isolada e determinística,
  recusas planejadas ou adicionais por saldo e timestamps UTC posteriores aos
  eventos de cartão.
- Pares imutáveis de débito e crédito para cada transferência concluída,
  validação de saldo sequencial e conservação do saldo agregado.
- Contrato batch `1.5.0` e gerador `0.6.0`, com `transfers.csv`, agregados de
  transferências no manifesto e publicação atômica dos oito CSVs.
- Ground truth determinístico e separado para cada tentativa original de compra,
  com padrões `high_amount`, `rapid_velocity` e `new_account_burst`, scores
  decimais e seed isolada.
- Contrato batch `1.6.0`, gerador `0.7.0` e rótulos `1.0.0`, com
  `transaction_labels.csv` integrado à publicação atômica dos nove CSVs.
- Cenários determinísticos e mutuamente exclusivos para duplicatas exatas,
  duplicatas conflitantes, nulos obrigatórios e FKs órfãs, derivados somente do
  conjunto canônico reconciliado.
- Contrato batch `1.6.1`, gerador `0.8.0` e contrato de qualidade `1.0.0`, com
  separação por `scenario=<nome>` e idempotência integral por cenário.

## Testes e validações disponíveis

- Carregamento da configuração padrão e verificação dos tipos resultantes.
- Casos de YAML inválido ou inseguro, arquivo inexistente e raiz inválida.
- Campos ausentes, propriedades desconhecidas e tipos ou valores inválidos.
- Limites inclusivos das taxas, intervalos invertidos, moeda, formato e diretório
  de saída.
- Determinismo, isolamento entre componentes, IDs, relações, cardinalidades,
  datas, tipos de conta, saldos de abertura e compatibilidade PyArrow.
- Conversão e round-trip CSV, escaping, UTF-8, cabeçalhos, ordem, datas,
  decimais, idempotência, atomicidade e segurança de caminhos.
- Pipeline completo, validação antes da escrita, determinismo, resumo da CLI,
  códigos de saída, erros conhecidos e preservação do diretório atual.
- Manifesto, checksums, tamanhos, contagens, serialização determinística,
  publicação por staging, falhas por fase, limpeza segura e conflitos.
- Geração, ordenação e validação do ledger, cálculo de créditos e débitos,
  reconciliação, timestamp UTC e compatibilidade com o schema PyArrow.
- Configuração, determinismo, isolamento, cardinalidade, chaves estrangeiras,
  datas, limites, bloqueio e schemas de cartões e estabelecimentos.
- pytest: 195 testes passando na execução atual com Python 3.14.4.
- Python 3.14.4 é a versão oficial de desenvolvimento e validação local. O
  pacote suporta Python `>=3.14,<3.15`.
- Ruff: lint e verificação de formatação passando, com alvo Python 3.14.

## Limitações conhecidas

- O ledger publicado contém aberturas, compras, estornos e transferências; saldos
  continuam derivados em memória e não são publicados como entidade independente.
- Somente transferências internas imediatas em BRL são suportadas; PIX,
  transferências externas, tarifas e agendamento permanecem fora do escopo.
- A fraude é uma classificação sintética baseada em três padrões controlados;
  não há geolocalização impossível, identidade roubada ou modelo de ML.
- A configuração aceita somente BRL e CSV.
- Combinação de cenários, corrupção monetária/contábil e streaming permanecem
  fora do escopo.

## Próxima etapa planejada

Ampliar cenários de qualidade em etapas separadas, preservando o conjunto
válido e sem combinar mutações nesta versão.

## Comandos principais

Preparar o ambiente e instalar o projeto com dependências de desenvolvimento:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Executar as verificações:

```bash
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

Validar a instalação e carregar a configuração atual:

```bash
python -c "import banking_data_generator as b; print(b.installation_status())"
python -c "from banking_data_generator.config import load_config; print(load_config('configs/default.yaml'))"
```

A CLI executa o pipeline batch atual com `python -m banking_data_generator`.
