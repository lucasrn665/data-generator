# Banking Data Generator

Gerador de dados bancários inteiramente sintéticos para exercícios de engenharia
de dados no Databricks. O projeto gera clientes, endereços e contas e permite
exportá-los em arquivos CSV batch; movimentações bancárias ainda não estão
implementadas.

## Requisitos

- Python 3.14.4 para desenvolvimento local; o pacote suporta Python
  `>=3.14,<3.15`
- `pip`

## Preparação do ambiente

Crie e ative um ambiente virtual fora deste repositório ou em `.venv` e, somente
depois, instale o projeto com as ferramentas de desenvolvimento:

```bash
python3.14 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Esses comandos são instruções para execução manual; o ambiente virtual e as
dependências não são criados automaticamente pelo projeto.

## Verificações

```bash
python -c "import banking_data_generator; print(banking_data_generator.installation_status())"
python -m pytest
python -m ruff check .
python -m ruff format --check .
```

## Configuração

[`configs/default.yaml`](configs/default.yaml) reserva os parâmetros comuns do
gerador. O diretório `data/output/` fica fora de `src/` e é ignorado pelo Git
para uso local. A exportação CSV usa diretórios determinísticos por data de
referência e seed. Toda geração recebe uma seed.

## Documentação

- [Modelo de domínio](docs/domain-model.md)
- [Regras de negócio](docs/business-rules.md)
- [Cenários de qualidade de dados](docs/data-quality-scenarios.md)

## Estado atual

Clientes, endereços, contas, schemas PyArrow e escrita batch CSV estão
implementados. Cartões, estabelecimentos, movimentações, ledger, saldo atual e
CLI permanecem fora do escopo atual.
