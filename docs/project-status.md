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

## Testes e validações disponíveis

- Carregamento da configuração padrão e verificação dos tipos resultantes.
- Casos de YAML inválido ou inseguro, arquivo inexistente e raiz inválida.
- Campos ausentes, propriedades desconhecidas e tipos ou valores inválidos.
- Limites inclusivos das taxas, intervalos invertidos, moeda, formato e diretório
  de saída.
- pytest: 30 testes passaram na última execução concluída, realizada com Python
  3.14.4 antes das alterações atuais. O teste do novo limite mínimo de contas
  foi adicionado, mas a suíte atual ainda precisa ser executada em um ambiente
  com pytest disponível.
- Ruff: lint e verificação de formatação passaram antes das alterações atuais;
  o alvo permanece configurado como Python 3.12. As verificações atuais ainda
  precisam ser executadas em um ambiente com Ruff disponível.
- A sintaxe foi analisada como Python 3.12, mas a suíte ainda deve ser executada
  em um interpretador Python 3.12 real. Essa verificação permanece pendente,
  mas não constitui bloqueio para o desenvolvimento local atual.

## Limitações conhecidas

- Clientes, endereços, contas, cartões, estabelecimentos, transações,
  transferências, ledger e saldos ainda não foram implementados.
- Ainda não existem CLI, geração de dados, schemas PyArrow ou escrita CSV.
- A configuração aceita somente BRL e CSV.
- A resolução de caminhos relativos a partir da raiz do projeto e a rejeição de
  saídas dentro de `src/` ainda não foram implementadas.
- Cenários de anomalia e streaming estão apenas documentados.

## Próxima etapa planejada

Definir schemas PyArrow, identificadores, enums e modelos mínimos de domínio
para clientes, endereços e contas, acompanhados de testes de tipos, unicidade e
integridade referencial. A etapa adotará um endereço principal por cliente,
contas dos tipos `checking` e `savings` e as cardinalidades documentadas. Cartões
e a geração de movimentações financeiras permanecem fora dessa etapa.

## Comandos principais

Preparar o ambiente e instalar o projeto com dependências de desenvolvimento:

```bash
python3.12 -m venv .venv
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

Ainda não existe um comando para gerar dados.
