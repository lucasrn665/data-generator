# Instruções do projeto

## Objetivo

Construir um gerador de dados bancários inteiramente sintéticos para
exercícios de engenharia de dados no Databricks.

## Domínio

- clientes
- endereços
- contas
- cartões sintéticos
- estabelecimentos
- transações
- transferências
- saldos

## Tecnologias

- Python 3.14.4
- Faker
- PyArrow
- PyYAML
- pytest
- Ruff

## Estrutura do projeto

- `configs/`: configurações versionadas e sem credenciais.
- `docs/`: modelo de domínio, regras de negócio e cenários de qualidade.
- `src/banking_data_generator/`: código-fonte do pacote.
- `tests/`: testes automatizados.
- Dados gerados devem ser gravados em um diretório externo ao código-fonte,
  configurado explicitamente pelo usuário.

## Regras

- Toda geração deve aceitar uma seed e ser reproduzível.
- Nenhum dado pode representar uma pessoa, documento, cartão ou conta real.
- Identificadores devem ser claramente sintéticos.
- Separar modelos de domínio, geração, validação e escrita de arquivos.
- Manter chaves estrangeiras consistentes.
- Usar Decimal para cálculos monetários internos.
- Não usar float para regras financeiras.
- Transações recusadas não alteram saldos.
- Estornos devem referenciar transações anteriores.
- Transferências devem manter consistência entre origem e destino.
- Não incluir credenciais no código.
- Não adicionar dependências sem justificar.
- Escrever testes para regras de negócio.
- Executar testes e lint depois das mudanças.
- Não criar ambientes virtuais nem instalar dependências sem autorização.
- Manter o README atualizado com os comandos de preparação, teste e lint.

## Escopo por etapa

- A estrutura inicial deve configurar o projeto, documentar o domínio planejado
  e fornecer apenas um módulo mínimo que permita validar a instalação.
- Clientes, contas, cartões, transações, transferências e saldos só devem ser
  implementados em etapas posteriores.
- Regras de negócio futuras devem estar documentadas antes da implementação e
  acompanhadas de testes quando forem introduzidas.

## Critério de conclusão da estrutura inicial

- A estrutura de diretórios e os arquivos de configuração estão presentes.
- O pacote mínimo pode ser importado e possui um teste básico.
- Os comandos de preparação, teste e lint estão documentados no README.
- As verificações disponíveis no ambiente foram executadas e reportadas.
- Nenhum dado de domínio é gerado nesta etapa.

## Critério de conclusão do gerador

- Todos os testes passam.
- As regras contábeis são validadas.
- Os comandos estão documentados no README.
- Os arquivos são gravados fora do código-fonte.
- Uma pequena amostra é gerada e validada.
- Um resumo das alterações é apresentado ao final.
