# FPS Arena

Sistema web para gestao de campeonatos de e-Sports com controle de acesso por perfil, provisionamento controlado de usuarios e isolamento entre organizadores.

## Visao Geral

O projeto foi refatorado para adotar um modelo RBAC com tres perfis:

- `SUPER_ADMIN`
  Responsavel pela plataforma. Pode criar contas de `ADMIN`, gerar codigo de acesso e senha inicial e visualizar o ambiente global.

- `ADMIN`
  Representa o organizador do campeonato. Nao faz cadastro livre. Entra no sistema por convite do `SUPER_ADMIN` e gerencia apenas os seus dados.

- `PLAYER`
  Usuario final vinculado a um organizador. Tem acesso de leitura ao proprio contexto e apenas aos campeonatos em que esta inscrito.

## Principais Regras Implementadas

- Nao existe cadastro livre de `ADMIN`.
- O `SUPER_ADMIN` cria contas de `ADMIN` com `codigo_acesso` unico.
- O `ADMIN` entra no primeiro acesso com `codigo + senha inicial`.
- O sistema obriga troca de senha no primeiro login do `ADMIN`.
- Jogadores sao provisionados pelo `ADMIN`, com `login` e `senha`.
- Todo dado sensivel e filtrado por `admin_id` no backend.
- Senhas sao armazenadas com `bcrypt`.

## Fluxos de Acesso

### 1. Fluxo do SUPER_ADMIN

1. Faz login com `login + senha`.
2. Acessa o painel de administracao.
3. Cria um novo `ADMIN`.
4. Recebe `codigo de acesso` e `senha inicial` gerados pelo sistema.

### 2. Fluxo do ADMIN

1. Recebe convite do `SUPER_ADMIN`.
2. Faz o primeiro login com `codigo de acesso + senha inicial`.
3. E redirecionado para trocar a senha obrigatoriamente.
4. Depois disso, passa a usar `login + senha`.
5. Pode criar campeonatos, times, jogadores e partidas apenas do seu escopo.

### 3. Fluxo do PLAYER

1. E criado pelo `ADMIN`.
2. Faz login com `login + senha`.
3. Visualiza somente o proprio perfil, time e campeonatos em que participa.

## Estrutura de Dados

### Usuario

- `id`
- `nome`
- `login`
- `senha_hash`
- `role` (`SUPER_ADMIN | ADMIN | PLAYER`)
- `admin_id`
- `player_id`
- `access_code`
- `access_code_expires_at`
- `must_change_password`
- `ativo`

### Campeonato

- `id`
- `nome`
- `admin_id`
- `jogo`
- `formato`
- `status` (`INSCRICAO | EM_ANDAMENTO | FINALIZADO`)

### Jogador

- `id`
- `nome`
- `nick`
- `login`
- `admin_id`
- `campeonato_id`

## Stack Tecnologica

- Python 3.10+
- Flask
- PyMongo
- MongoDB
- Redis para cache opcional
- Jinja2
- HTML/CSS
- bcrypt

## Estrutura do Projeto

```text
fps_arena/
|-- app.py
|-- seed_db.py
|-- requirements.txt
|-- app/
|   |-- application/
|   |-- infrastructure/
|   |-- interfaces/
|   `-- factory.py
|-- templates/
|   |-- base.html
|   |-- dashboard.html
|   |-- login.html
|   |-- ranking.html
|   |-- relatorios.html
|   |-- campeonatos/
|   |-- jogadores/
|   |-- times/
|   `-- usuarios/
`-- docs/
```

## Instalacao e Execucao

### Pre-requisitos

- Python 3.10+
- MongoDB local em execucao
- Redis local em execucao, opcional. Se estiver desligado, o sistema usa `NoCache`.
- `pip`

### Passos

```bash
cd fps_arena
pip install -r requirements.txt
python seed_db.py
python app.py
```

Para rodar os testes automatizados:

```bash
pip install -r requirements-dev.txt
pytest
```

Ou, no Windows, com um comando mais direto:

```powershell
.\start_windows.ps1 -Install -Seed
```

Ou usando Python:

```bash
python run_local.py --install --seed
```

Depois da primeira execucao, voce pode subir sem recriar a base:

```powershell
.\start_windows.ps1
```

Aplicacao:

```text
http://localhost:5000
```

## Dicas de Execucao no Seu PC

- Se o projeto abrir erro de MongoDB, confirme que o servico do Mongo esta rodando localmente.
- Se o Redis nao estiver rodando, a aplicacao continua funcionando sem cache.
- O ranking usa cache no Redis com chaves `fps_arena:ranking:*`.
- Se quiser desligar o cache explicitamente: `$env:REDIS_ENABLED="false"`
- Se quiser usar outra porta: `.\start_windows.ps1 -Port 5001`
- Se a base estiver baguncada e voce quiser recomecar: `.\start_windows.ps1 -Seed`

## Base de Perfis de Teste

Depois de executar `python seed_db.py`, o projeto cria uma base com os tres perfis do sistema:

### Perfil 1: SUPER_ADMIN

- Login: `superadmin`
- Senha: `super123`
- Uso: dono da plataforma, cria contas de `ADMIN`

### Perfil 2: ADMIN

- Login normal: `arena.demo`
- Senha inicial: `admin123`
- Primeiro acesso: `codigo de acesso + admin123`
- Uso: organizador que gerencia campeonatos, jogadores, times e partidas do proprio escopo

Observacao:
o codigo de acesso do `ADMIN` e gerado dinamicamente no `seed_db.py` e exibido no terminal ao executar a seed.

### Perfil 3: PLAYER

- Login: `carlos_snipe`
- Senha: `jogador1`
- Uso: jogador com acesso somente leitura ao proprio contexto

## Dados de Exemplo Criados Pela Seed

O `seed_db.py` cria:

- 1 conta `SUPER_ADMIN`
- 1 conta `ADMIN`
- 6 jogadores
- 3 times
- 2 campeonatos
- 1 partida

Isso deixa uma base pronta para demonstrar:

- criacao de `ADMIN` por convite
- primeiro acesso com troca obrigatoria de senha
- isolamento por organizador
- acesso restrito de `PLAYER`

## Seguranca Aplicada

- validacao de role no backend
- filtros por `admin_id`
- troca obrigatoria de senha no primeiro acesso do `ADMIN`
- senha criptografada com `bcrypt`
- restricao de visibilidade para `PLAYER`

## Observacao

Se houver dados legados no banco, a aplicacao executa uma migracao automatica basica para adaptar usuarios, campeonatos e relacionamentos ao novo modelo.
