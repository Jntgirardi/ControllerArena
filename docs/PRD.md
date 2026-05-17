# PRD Simplificado - FPS Arena

## 1. Nome do Sistema

**FPS Arena**

Plataforma web para gestão de campeonatos de e-Sports com foco inicial em CS2 e Valorant.

## 2. Problema

Organizadores de campeonatos amadores e universitários ainda dependem de planilhas, mensagens manuais e controles descentralizados para gerenciar inscrições, confrontos, partidas e resultados. Isso gera retrabalho, falhas operacionais e baixa visibilidade para jogadores e público.

## 3. Solução

O FPS Arena centraliza o fluxo principal do campeonato em uma única aplicação web:

- cadastro de jogadores
- formação de times
- criação de campeonatos
- inscrição de equipes
- consulta de partidas
- ranking
- relatórios operacionais

## 4. Finalidade do Produto

Entregar um sistema funcional que permita ao organizador conduzir campeonatos de forma mais estruturada, com menor dependência de controles paralelos.

## 5. Público-Alvo

- organizadores de campeonatos universitários
- arenas gamers
- comunidades competitivas locais
- jogadores e equipes participantes

## 6. Persona Principal

**Rafael, 26 anos, organizador de torneios locais**

- organiza campeonatos de FPS em arenas e eventos universitários
- usa planilhas e mensagens para coordenar equipes
- perde tempo controlando vagas, confrontos e resultados manualmente
- precisa de uma solução centralizada e simples de operar

## 7. Matriz de Usuários

### Administrador

- acesso total ao sistema
- cria campeonatos
- define regras
- cadastra usuários
- gerencia jogadores, times e resultados

### Operador / Jogador

- consulta informações do campeonato
- inscreve times
- acompanha partidas, ranking e resultados

### Público Geral

- acompanha ranking e informações publicadas

## 8. Proposta de Valor

- menos retrabalho operacional
- maior organização do evento
- melhor visibilidade para participantes
- base pronta para crescimento do produto

## 9. Funcionalidades do MVP

- autenticação por perfil
- dashboard com visão geral
- CRUD de jogadores
- CRUD de times
- CRUD de campeonatos
- inscrição de times em campeonatos
- visualização de partidas
- ranking geral
- relatório por período

## 10. Critérios de Liberação do MVP

O MVP estará pronto para apresentação quando:

- o administrador conseguir criar um campeonato completo
- um time puder ser inscrito com sucesso
- o sistema exibir os dados do campeonato e das partidas
- o ranking estiver funcional
- o fluxo principal estiver demonstrável de ponta a ponta

## 11. Restrições e Premissas

- foco inicial em CS2 e Valorant
- uso local de MongoDB no ambiente acadêmico
- autenticação e perfis suficientes para o escopo do MVP

## 12. Próximos Passos Pós-MVP

- bracket visual automatizado
- notificações
- check-in em partidas
- painel público expandido
- métricas operacionais mais avançadas
