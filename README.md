# FPS Arena

## Sobre o trabalho

O FPS Arena e um sistema web desenvolvido para organizar campeonatos de e-Sports, com foco em jogos de FPS como CS2 e Valorant. O objetivo do trabalho e facilitar a administracao de campeonatos, jogadores, times e partidas em uma plataforma simples, funcional e com controle de acesso por perfil.

O projeto foi pensado para resolver um problema comum em competicoes: a falta de uma ferramenta centralizada para cadastrar participantes, montar equipes, acompanhar campeonatos e separar as permissoes de cada tipo de usuario.

## Objetivo do sistema

O principal objetivo do FPS Arena e permitir que organizadores criem e gerenciem campeonatos de forma segura. Cada usuario acessa apenas as informacoes permitidas pelo seu perfil, evitando que dados de outros organizadores ou jogadores sejam exibidos indevidamente.

Com isso, o sistema demonstra conceitos importantes de desenvolvimento web, banco de dados, seguranca, controle de acesso e organizacao de regras de negocio.

## Funcionalidades principais

- Login de usuarios com controle de permissao.
- Cadastro e gerenciamento de campeonatos.
- Cadastro de jogadores.
- Cadastro de times.
- Vinculo entre jogadores, times e campeonatos.
- Controle de partidas.
- Dashboard com informacoes gerais.
- Ranking e relatorios.
- Separacao de acesso entre administrador da plataforma, organizador e jogador.
- Uso de MongoDB para persistencia dos dados.
- Uso de Redis para cache quando disponivel.

## Perfis de usuario

O sistema possui tres tipos principais de usuario:

### SUPER_ADMIN

E o administrador principal da plataforma. Ele pode criar contas de administradores, gerar convite de acesso e visualizar a estrutura geral do sistema.

### ADMIN

E o organizador do campeonato. Ele gerencia seus proprios jogadores, times, campeonatos e partidas. Cada administrador trabalha apenas com os dados do seu proprio contexto.

### PLAYER

E o jogador cadastrado por um administrador. Ele acessa suas informacoes, seu time e os campeonatos nos quais esta envolvido.

## Tecnologias utilizadas

- Python
- Flask
- MongoDB
- PyMongo
- Redis
- Jinja2
- HTML
- CSS
- Bootstrap
- bcrypt
- pytest

## Estrutura do projeto

```text
fps_arena/
|-- app.py
|-- seed_db.py
|-- run_local.py
|-- requirements.txt
|-- requirements-dev.txt
|-- app/
|   |-- application/
|   |-- domain/
|   |-- infrastructure/
|   |-- interfaces/
|   `-- factory.py
|-- templates/
|-- tests/
`-- docs/
```

## Banco de dados e cache

O sistema utiliza MongoDB como banco de dados principal. Nele ficam armazenados usuarios, jogadores, times, campeonatos e partidas.

O Redis e utilizado como cache para melhorar o desempenho em consultas que podem ser reaproveitadas, como ranking. Caso o Redis nao esteja ativo, o sistema continua funcionando sem cache.

## Como executar o projeto

Antes de iniciar, e necessario ter o Python instalado e o MongoDB em execucao. O Redis e recomendado, mas opcional.

Instale as dependencias:

```bash
pip install -r requirements.txt
```

Crie a base inicial de teste:

```bash
python seed_db.py
```

Inicie o sistema:

```bash
python app.py
```

Depois, acesse no navegador:

```text
http://localhost:5000
```

No Windows, tambem e possivel executar com:

```powershell
.\start_windows.ps1 -Install -Seed
```

## Usuarios de teste

A seed do projeto cria usuarios e dados iniciais para demonstracao.

### Super administrador

- Login: `superadmin`
- Senha: `super123`

### Administrador

- Login: `arena.demo`
- Senha inicial: `admin123`

### Jogador

- Login: `carlos_snipe`
- Senha: `jogador1`

## Testes

Para instalar as dependencias de desenvolvimento:

```bash
pip install -r requirements-dev.txt
```

Para executar os testes:

```bash
pytest
```

## Conclusao

O FPS Arena representa um sistema completo para gestao de campeonatos de e-Sports. O trabalho aplica conceitos de desenvolvimento web, arquitetura em camadas, banco de dados NoSQL, cache, autenticacao, autorizacao e organizacao de regras de negocio.

Com esse projeto, e possivel demonstrar uma aplicacao pratica, com perfis de usuario bem definidos e funcionalidades voltadas para uma necessidade real dentro do ambiente competitivo de jogos eletronicos.
