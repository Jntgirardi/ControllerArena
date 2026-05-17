# Product Backlog - FPS Arena

## Backlog Priorizado

### FPS-01 - Tela de login do usuário

- Como usuário do sistema, eu quero realizar login para acessar as funcionalidades do meu perfil.
- Assignee: Douglas Cerqueira
- Prioridade: Alta
- Sprint: 2
- Critérios de aceite:
- autenticar com usuário e senha válidos
- negar acesso com credenciais inválidas
- redirecionar para dashboard após login

### FPS-02 - Dashboard com visão geral do sistema

- Como administrador, eu quero visualizar métricas rápidas do sistema para acompanhar a operação.
- Assignee: Leonardo Souza
- Prioridade: Alta
- Sprint: 2
- Critérios de aceite:
- exibir total de jogadores, times, campeonatos e partidas
- exibir campeonatos recentes
- restringir acesso a usuários autenticados

### FPS-03 - Cadastro de jogadores

- Como administrador, eu quero cadastrar jogadores para montar times e campeonatos.
- Assignee: Douglas Cerqueira
- Prioridade: Alta
- Sprint: 2
- Critérios de aceite:
- cadastrar nick, nome real e jogo principal
- validar campos obrigatórios
- impedir nick duplicado

### FPS-04 - Edição e remoção de jogadores

- Como administrador, eu quero editar ou remover jogadores para manter os dados atualizados.
- Assignee: Douglas Cerqueira
- Prioridade: Média
- Sprint: 2
- Critérios de aceite:
- permitir edição dos dados do jogador
- atualizar informações com sucesso
- remover jogador e refletir alteração no sistema

### FPS-05 - Cadastro de times

- Como administrador, eu quero criar times com jogadores cadastrados para permitir inscrição em campeonatos.
- Assignee: Leonardo Souza
- Prioridade: Alta
- Sprint: 2
- Critérios de aceite:
- selecionar jogadores existentes
- salvar nome e tag do time
- impedir criação inconsistente

### FPS-06 - Cadastro de campeonatos

- Como administrador, eu quero criar campeonatos para abrir inscrições e organizar partidas.
- Assignee: Jonathas Girardi
- Prioridade: Alta
- Sprint: 3
- Critérios de aceite:
- definir nome, jogo, datas e limite de equipes
- validar datas e quantidade mínima de times
- salvar campeonato com status inicial

### FPS-07 - Inscrição de times em campeonatos

- Como operador, eu quero inscrever times em campeonatos abertos para confirmar participação.
- Assignee: Lucas Câmera
- Prioridade: Alta
- Sprint: 3
- Critérios de aceite:
- permitir inscrição somente em campeonatos abertos
- impedir times duplicados
- impedir inscrição acima do limite de vagas

### FPS-08 - Visualização de detalhes do campeonato

- Como usuário, eu quero ver detalhes do campeonato para acompanhar o evento.
- Assignee: Leonardo Souza
- Prioridade: Alta
- Sprint: 3
- Critérios de aceite:
- mostrar dados do campeonato
- listar times inscritos
- listar partidas relacionadas

### FPS-09 - Registro de resultados de partidas

- Como administrador, eu quero registrar resultados para manter o torneio atualizado.
- Assignee: Douglas Cerqueira
- Prioridade: Alta
- Sprint: 3
- Critérios de aceite:
- permitir salvar vencedor e placar
- refletir status nas partidas
- manter os dados consistentes

### FPS-10 - Ranking geral de jogadores

- Como usuário, eu quero visualizar o ranking para acompanhar desempenho dos jogadores.
- Assignee: Lucas Câmera
- Prioridade: Média
- Sprint: 3
- Critérios de aceite:
- ordenar jogadores por desempenho
- permitir consulta autenticada
- exibir dados sem erro de paginação ou carregamento

### FPS-11 - Relatórios por período

- Como administrador, eu quero consultar campeonatos por período para apoiar acompanhamento operacional.
- Assignee: Jonathas Girardi
- Prioridade: Média
- Sprint: 4
- Critérios de aceite:
- filtrar campeonatos por data
- exibir resultados coerentes com o filtro
- manter desempenho adequado no ambiente local

### FPS-12 - Gestão de usuários do sistema

- Como administrador, eu quero cadastrar usuários para controlar acessos e permissões.
- Assignee: André Góes
- Prioridade: Média
- Sprint: 4
- Critérios de aceite:
- criar usuário com perfil
- impedir duplicidade de username
- restringir acesso administrativo corretamente
