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
- A rejeição de caminhos de saída dentro de `src/` será implementada em uma
  etapa futura de validação de segurança de caminhos.

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
- Escrita batch determinística de `customers.csv`, `addresses.csv` e
  `accounts.csv`, com substituição atômica individual e limpeza do temporário
  próprio em caso de falha.
- Resolução do diretório de saída pela raiz do projeto e rejeição de caminhos
  absolutos, travessias, escapes e destinos dentro de `src/` ou `.git/`.

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
- pytest: 57 testes passando na execução atual com Python 3.14.4.
- Python 3.14.4 é a versão oficial de desenvolvimento e validação local. O
  pacote suporta Python `>=3.14,<3.15`.
- Ruff: lint e verificação de formatação passando, com alvo Python 3.14.

## Limitações conhecidas

- Cartões, estabelecimentos, transações, transferências, ledger e saldos atuais
  ainda não foram implementados.
- Ainda não existem CLI ou schemas PyArrow para entidades futuras.
- A configuração aceita somente BRL e CSV.
- Cenários de anomalia e streaming estão apenas documentados.

## Próxima etapa planejada

Definir o próximo incremento antes de implementar novas entidades. Uma camada
de orquestração ou cartões são candidatos naturais; eventos financeiros,
ledger e saldo atual permanecem fora da etapa concluída.

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

Ainda não existe uma CLI para gerar dados.
