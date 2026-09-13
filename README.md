# Banking Data Generator

Gerador de dados bancários inteiramente sintéticos para exercícios de engenharia
de dados no Databricks. O projeto gera clientes, endereços, contas, cartões de
débito, estabelecimentos, compras, estornos, transferências internas e
ground truth sintético de fraude e lançamentos contábeis em um conjunto batch
com nove CSVs e manifesto.

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
`transactions.csv`, `transaction_labels.csv`, `transfers.csv`,
`ledger_entries.csv` e `manifest.json` no diretório
particionado por versão do schema, data de referência, seed e cenário `valid`.
O conjunto é publicado de uma só vez; uma reexecução idêntica valida os arquivos
existentes sem sobrescrevê-los. O layout é
`data/output/schema_version=1.7.1/reference_date=YYYY-MM-DD/seed=N/scenario=valid/`.

Use `--scenario` para publicar, separadamente, `duplicate_exact`,
`duplicate_conflicting`, `required_null`, `orphan_foreign_key`, `late_event`,
`schema_additive_column`, `schema_missing_column`, `schema_renamed_column`,
`schema_incompatible_value` ou `schema_unknown_enum`. Sem a opção,
o cenário é `valid`. Todos mantêm os mesmos nove CSVs; somente o CSV alvo e o
manifesto diferem do conjunto canônico.

Em `transactions.csv`, `event_at` representa a ocorrência econômica e
`ingested_at` representa a chegada à plataforma. O cenário válido usa atraso
operacional configurado de 0 a 30 segundos; `late_event` seleciona, com cota
`ROUND_HALF_UP`, eventos cuja chegada ultrapassa o limite configurado de 300
segundos e ordena fisicamente o CSV por chegada. A contabilidade permanece
ordenada pelo instante econômico. Esta simulação prepara exercícios futuros de
watermark e dados fora de ordem, sem implementar Spark, Databricks ou streaming.

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
implementados. Compras aprovadas geram débitos; recusas não alteram saldo nem
limite diário. Estornos integrais são eventos separados que geram créditos e
restauram saldo e limite. Transferências internas concluídas geram um débito e
um crédito de mesmo valor; recusas não alteram o ledger e o total é conservado.
O rótulo de fraude não aparece em `transactions.csv`: o ground truth separado
fica em `transaction_labels.csv`.
Os cartões não contêm PAN, CVV, senha ou outra credencial bancária.
