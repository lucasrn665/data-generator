# Banking Data Generator

Estrutura inicial de um gerador de dados bancários inteiramente sintéticos para
exercícios de engenharia de dados no Databricks. Nesta etapa, o projeto apenas
valida a instalação do pacote; nenhuma entidade ou movimentação bancária é
gerada.

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
para uso local. O formato inicial de saída é CSV. Toda geração futura deverá
receber uma seed.

## Documentação

- [Modelo de domínio](docs/domain-model.md)
- [Regras de negócio](docs/business-rules.md)
- [Cenários de qualidade de dados](docs/data-quality-scenarios.md)

## Estado atual

Ainda não há implementação de clientes, endereços, contas, cartões,
estabelecimentos, transações, transferências ou saldos.
