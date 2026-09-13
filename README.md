# Banking Data Generator

Gerador de dados bancários inteiramente sintéticos para exercícios de engenharia
de dados no Databricks. O projeto gera clientes, endereços, contas, cartões de
débito, estabelecimentos e lançamentos de abertura em um conjunto batch com seis
CSVs e manifesto de integridade.

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

## Execução batch

Execute o pipeline completo a partir da raiz do projeto:

```bash
python -m banking_data_generator --config configs/default.yaml
```

Use `--project-root` quando a raiz desejada não for o diretório atual. A CLI
carrega a configuração, gera e valida os dados e escreve `customers.csv`,
`addresses.csv`, `accounts.csv`, `cards.csv`, `merchants.csv`,
`ledger_entries.csv` e `manifest.json` no diretório particionado por versão do
schema, data de referência, seed e cenário `valid`. O conjunto é publicado de
uma só vez; uma reexecução idêntica
valida os arquivos existentes sem sobrescrevê-los. O layout é
`data/output/schema_version=1.2.0/reference_date=YYYY-MM-DD/seed=N/scenario=valid/`.

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

Clientes, endereços, contas, cartões exclusivamente de débito, estabelecimentos,
schemas PyArrow, publicação batch atômica com manifesto, pipeline e CLI estão
implementados. Movimentações e transferências permanecem fora do escopo atual.
Os cartões não contêm PAN, CVV, senha ou outra credencial bancária.
