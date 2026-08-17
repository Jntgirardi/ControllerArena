# FPS Arena 🎮🔥
## Guia de Funcionalidades e Específicações de Interface (UI/UX)

Este documento descreve detalhadamente todas as funcionalidades do **FPS Arena**, seus fluxos de operação passo a passo e as especificações de tela. Ele foi estruturado para servir como um guia completo para o designer responsável pelo remodelamento da interface (frontend) do sistema.

---

## 👥 1. Perfis de Usuário e Níveis de Acesso

O sistema possui cinco níveis de acesso, cada um com visões e permissões específicas que o layout do frontend deve refletir:

1.  **SUPER_ADMIN (Super Administrador):** Possui controle total da infraestrutura, gera convites de primeiro acesso para organizadores (ADMINs), remove contas e gerencia logs gerais do sistema.
2.  **ADMIN (Organizador do Torneio):** Cadastra campeonatos, equipes, jogadores e árbitros. Organiza as chaves das partidas (brackets), altera status do campeonato, configura check-ins e força confirmações manuais.
3.  **REFEREE (Árbitro):** Visualiza as partidas atribuídas a ele, controla a súmula em tempo real round a round e finaliza as partidas preenchendo o KDA de cada jogador.
4.  **PLAYER (Jogador / Capitão):** Acessa o painel personalizado contendo estatísticas (K/D, Win Rate), histórico de partidas e confirma a presença da sua equipe (Check-in) quando o Capitão.
5.  **VISITANTE (Público):** Acessa o Lobby geral, visualiza as chaves do campeonato, lê as súmulas públicas detalhadas de partidas e consulta os rankings globais.

---

## 🔄 2. Fluxos de Operação Passo a Passo (User Flows)

Abaixo estão descritos os 5 fluxos centrais da aplicação que demandam transições e interações de interface bem projetadas.

### Fluxo 1: Ciclo de Vida do Campeonato (Administrador)
1.  **Cadastro:** O ADMIN acessa `Campeonatos > Novo` e preenche o formulário (Nome, Jogo [CS2/Valorant], Formato [Mata-mata/Grupos], Limite de Equipes, Datas de Início/Fim, Premiações e Discord Webhook).
2.  **Inscrição de Equipes:** Na página de detalhes do campeonato, enquanto o status for `Inscrição`, o ADMIN pode buscar e adicionar equipes na lista de inscritos.
3.  **Geração de Brackets:** Com a quantidade de equipes definida, o ADMIN clica em **"Gerar Confrontos"**. O sistema cria a chave de partidas automaticamente no formato mata-mata.
4.  **Iniciar Competição:** O ADMIN altera o status do campeonato para `Em andamento`. A partir deste momento, as partidas podem ter seus check-ins iniciados.
5.  **Encerramento:** Após todas as partidas serem concluídas, o status é alterado para `Finalizado`, travando novas modificações e recalculando os rankings.

### Fluxo 2: Confirmação de Presença e Controle de W.O. (Jogador e Administrador)
1.  **Configuração de Check-in (ADMIN):** Na partida agendada, o ADMIN clica em **"Configurar Check-in"**, escolhe a antecedência (ex: 30 minutos antes do jogo) e ativa.
2.  **Notificação e Botão (Jogador):** Os jogadores das duas equipes recebem um alerta piscando no dashboard. Se o jogador logado for o **Capitão** do time, um botão destacado **"CONFIRMAR PRESENÇA"** fica ativo.
3.  **Confirmação:** O Capitão clica no botão, e o status da presença da equipe muda para verde ("Confirmado") na súmula.
4.  **Verificação de Limite e W.O. (ADMIN):** Caso o tempo limite estipulado termine e uma ou ambas as equipes não tenham confirmado a presença, o ADMIN clica em **"Verificar W.O. / Ausência"**. O sistema aplica a derrota por W.O. automaticamente ao time faltante (16x0 no placar) e notifica o Discord configurado.

### Fluxo 3: Arbitragem e Lançamento de Rounds em Tempo Real (Árbitro)
1.  **Acesso à Partida:** O Árbitro entra em seu painel (`Painel do Árbitro`) e clica em **"Iniciar Arbitragem"** na sua partida designada.
2.  **Interface de Rounds:** A tela exibe o placar grande (`0 x 0`) e o painel de lançamento.
3.  **Lançamento de Round:**
    *   O árbitro clica no botão com o **Nome da Equipe** que venceu o round.
    *   Seleciona a **Condição de Vitória** no dropdown (ex: *Eliminação*, *Explosão da C4 / Spike*, *Desarmamento*, *Tempo Esgotado*).
    *   Clica em **"Confirmar Round"**.
    *   O placar é atualizado no banco de dados e sincronizado na súmula pública em tempo real. O round aparece na lista de "Rounds Anteriores".
4.  **Desfazer Erro:** Caso o árbitro erre o vencedor, ele pode clicar em **"Desfazer"** no round correspondente no feed. O sistema remove o round e reajusta o placar.
5.  **Finalização da Partida:** Ao atingir o placar final ou ao decidir encerrar, o Árbitro clica em **"Finalizar Partida"**.
6.  **Lançamento de KDA (Modal Obrigatório):** Abre-se um modal listando os jogadores do Time A e do Time B. O árbitro insere os abates (Kills), mortes (Deaths) e assistências (Assists) de cada jogador e clica em "Salvar".
7.  **Conclusão:** O sistema grava a súmula finalizada, invalida o cache de rankings no Redis para recalcular os dados e redireciona o árbitro de volta ao campeonato.

---

## 📺 3. Dicionário de Telas e Especificações de UI

### Tela 1: Lobby Público (HLTV-style Home)
*   **Finalidade:** Apresentação da liga e lobby de jogos para visitantes e torcedores.
*   **Componentes Visuais:**
    *   **Hero Section:** Banner gamer contendo a logo do FPS Arena, slogan e dois botões rápidos ("Ver Campeonatos" e "Partidas Ao Vivo").
    *   **Grid de Campeonatos Ativos:** Cards contendo imagem de capa do jogo (CS2 ou Valorant), título do campeonato, status destacado (Inscrição, Em Andamento, Finalizado), total de equipes inscritas e valor da premiação.
    *   **Partidas Ao Vivo:** Cards em destaque contendo uma bolinha vermelha piscando (**"AO VIVO"**), fase da partida, nome das equipes com placares em destaque vermelho neon e botão discreto "Ver Súmula".
    *   **Próximas Partidas:** Lista horizontal ou vertical de partidas com a tag azul "AGENDADO", exibindo equipes, mapa, data e hora em fonte monoespaçada.
    *   **Resultados Recentes:** Lista de partidas finalizadas mostrando os placares finais (com destaque em verde para o vencedor) e link para a súmula correspondente.

### Tela 2: Dashboard do Jogador (PLAYER)
*   **Finalidade:** Espaço exclusivo do atleta para gerenciar sua rotina de partidas e acompanhar seus números.
*   **Componentes Visuais:**
    *   **Profile Card:** Nome/Nick do atleta, escudo do time atual, indicação se é capitão e um indicador verde de "Online".
    *   **Card de Check-in de Emergência (Notificação de Próximo Jogo):** Banner com borda vermelha neon que aparece apenas quando o check-in do seu próximo jogo estiver aberto. Contém contagem regressiva e um botão centralizado grande **"CONFIRMAR PRESENÇA"**.
    *   **Histórico Recente de Jogos:** Lista de cards compactos com o resultado das últimas partidas do jogador.
    *   **Grade de Estatísticas de Desempenho (Stats Cards):** Quatro caixas destacando:
        1.  *Vitórias* (número verde)
        2.  *Derrotas* (número vermelho)
        3.  *Win Rate* (percentual amarelo)
        4.  *K/D Ratio* (valor decimal destacado)

### Tela 3: Painel do Árbitro (REFEREE)
*   **Finalidade:** Hub de controle de escala e partidas atribuídas ao árbitro.
*   **Componentes Visuais:**
    *   **Header:** Nome do árbitro e badge de notificações/alertas pendentes.
    *   **Card de Próxima Arbitragem:** Destaque de partida agendada de forma iminente, contendo botões para "Iniciar Arbitragem" e "Ver Check-in".
    *   **Tabela de Partidas Designadas:**
        *   Colunas: Partida (Time A vs Time B), Fase, Data/Hora, Mapa, Status (Agendado, Ao Vivo, Finalizado) e Ação.
        *   Ação: Botão vermelho "Arbitrar" para partidas não finalizadas; texto cinza "Finalizada" para partidas já concluídas.
    *   **Painel de Alertas:** Lista de notificações sobre alterações de horários ou check-ins pendentes com botão individual para marcar como lido ("X").

### Tela 4: Painel do Administrador (ADMIN / SUPER_ADMIN)
*   **Finalidade:** Dashboard gerencial com métricas rápidas e atalhos de cadastro.
*   **Componentes Visuais:**
    *   **Indicadores Rápidos (Stats Counters):** Quatro cards de contagem total com ícones representativos: Jogadores cadastrados, Times cadastrados, Campeonatos e Partidas organizadas.
    *   **Tabela de Campeonatos Recentes:** Nome, Jogo, Formato, Times inscritos (ex: `10 / 16`), Status (badge colorido) e link direto "Ver detalhes".
    *   **Atalhos Rápidos (Quick Actions):** Grade de botões ilustrados para:
        *   *Criar Campeonato* (ícone de troféu)
        *   *Cadastrar Jogador* (ícone de perfil com "+")
        *   *Cadastrar Time* (ícone de escudo com "+")
    *   **Alertas de Jogos:** Feed de eventos em tempo real (ex: "Time A confirmou presença", "Partida Finalizada pelo Árbitro").

### Tela 5: Detalhes do Campeonato (Público / Organizador)
*   **Finalidade:** Visualizar a situação geral de um torneio, suas chaves, participantes e controle administrativo de partidas.
*   **Componentes Visuais:**
    *   **Sidebar Informativo:** Tabela vertical detalhando: Formato, Times Inscritos, Datas e Link do Discord.
    *   **Painel Administrativo de Status (Apenas ADMIN):** Caixa com seletor Dropdown para alterar o status do campeonato e botão "Atualizar".
    *   **Card de Times Inscritos:**
        *   Lista contendo o logo do time, tag do jogo, nome do time.
        *   Botão "Desinscrever" (X) ao lado de cada time (apenas ADMIN, antes do início).
        *   Dropdown de seleção rápida de times não inscritos com botão "Adicionar" para inscrição manual rápida (apenas ADMIN).
    *   **Card de Partidas e Chaves:**
        *   Botão destacado **"Gerar Confrontos"** (visível apenas na fase de Inscrição se nenhuma partida existir).
        *   Botão **"Agendar"** que expande o formulário de criação manual de partidas.
        *   *Formulário Nova Partida:* Inputs para Fase, Seleção de Time A, Seleção de Time B, Mapa, Dropdown de Árbitro e campo Data/Hora.
        *   *Lista de Partidas Geradas:*
            *   Cada partida exibe: Fase, Mapa, Placar (`Time A x Time B`), Árbitro atribuído.
            *   Se check-in ativo: Mostra badges "Confirmado" (verde) ou "Pendente" (amarelo) para cada time.
            *   Botão **"Configurar Check-in"** (ou "Verificar W.O.") para ADMINs.
            *   Botão **"Controlar Rounds"** para Árbitros/ADMINs.
            *   Formulário de preenchimento manual rápido de placar (Inputs Placar A/B + botão salvar).

### Tela 6: Súmula Pública de Partida
*   **Finalidade:** Exibir os detalhes técnicos de um confronto finalizado ou em tempo real para o público em geral.
*   **Componentes Visuais:**
    *   **Painel Superior do Placar (Scoreboard Band):** Placar centralizado gigante com o status da partida (Finalizado, Ao Vivo, Agendado), nome das equipes e escudos grandes.
    *   **Rodapé do Placar:** Detalhes de mapa, fase do campeonato e data/hora.
    *   **Rounds Log:** Lista cronológica dos rounds. Cada linha exibe: número do round (ex: *Round 1*), nome e escudo da equipe vencedora (cor correspondente) e badge do método de vitória (ex: *Desarmamento*, *Eliminação*).
    *   **Tabelas de KDA dos Jogadores:** Duas tabelas posicionadas lado a lado (uma para cada equipe):
        *   Colunas: Jogador (Nick), Abates (K), Mortes (D), Assistências (A) e KDA Ratio (K+A/D).
        *   **Badge MVP:** Badge dourada aplicada ao jogador de melhor desempenho (Kills >= 15 e vencedor do jogo).

### Tela 7: Rankings e Classificações (Leaderboard)
*   **Finalidade:** Exibir os rankings globais de jogadores e times da plataforma.
*   **Componentes Visuais:**
    *   **Abas de Navegação:** Botões grandes para alternar entre aba "Jogadores" e aba "Times".
    *   **Dropdown de Filtro de Jogo:** Seletor (Todos, CS2, Valorant) posicionado à direita.
    *   **Podium (Top 3):** Destaque visual tridimensional para os três primeiros colocados:
        *   *#1 Lugar (Centro):* Card maior, borda dourada, ícone de troféu de ouro, nick do jogador/time, escudo e estatísticas principais.
        *   *#2 Lugar (Esquerda):* Card médio, borda cinza, ícone de estrela de prata.
        *   *#3 Lugar (Direita):* Card menor, borda de bronze.
    *   **Tabela Geral de Classificação:**
        *   Tabela com listagem ordenada a partir da 4ª colocação.
        *   Colunas Jogadores: Posição, Nick, Equipe, Badge do Jogo, Vitórias, Derrotas, Win Rate (%) e K/D Ratio.
        *   Colunas Times: Posição, Nome do Time, Tag, Badge do Jogo, Vitórias, Derrotas e Win Rate (%).

### Tela 8: Interface de Controle de Rounds em Tempo Real (Arbitragem)
*   **Finalidade:** Ferramenta interativa e dinâmica para uso exclusivo do árbitro durante a condução da partida.
*   **Componentes Visuais:**
    *   **Scoreboard Central:** Placar gigante atualizado dinamicamente via requisições AJAX/JSON.
    *   **Painel "Registrar Round" (Caixa Vermelha Neon):**
        *   Título grande informando o round atual (ex: *Round 12*).
        *   Dois botões grandes com os nomes dos times para seleção rápida de vencedor. O botão selecionado ganha destaque de cor ativa.
        *   Seletor de Método de Vitória: Campo Dropdown estilizado.
        *   Botão **"Confirmar Round"**: Botão vermelho que inicia desabilitado e só destrava quando o vencedor e o método forem selecionados.
    *   **Lista de Rounds Anteriores (Feed Vertical):** Linhas contendo as informações dos rounds passados e um botão de ação rápida "Desfazer".
    *   **Modal de Finalização e Entrada de KDA:**
        *   Disparado ao clicar em "Finalizar Partida" na barra superior.
        *   Exibe o placar final e dois blocos de inputs.
        *   Cada bloco contém o nome do jogador e campos numéricos sequenciais para digitação rápida de Kills, Deaths e Assists.
        *   Botão "Finalizar e Salvar Resultados" na parte inferior.

### Tela 9: Central de Relatórios (ADMIN / SUPER_ADMIN)
*   **Finalidade:** Painel para filtragem de estatísticas e exportação de relatórios.
*   **Componentes Visuais:**
    *   **Filtros de Data:** Inputs de tipo "Data Início" e "Data Fim" seguidos por botões de ação "Filtrar" e "Limpar".
    *   **Grade de Relatórios Disponíveis:** Cards representando os relatórios estruturados (ex: *Logs do Sistema*, *Desempenho Geral de Equipes*, *Artilharia de Jogadores*).
    *   **Indicadores de Métricas Rápidas:** Cards internos em cada relatório resumindo contadores importantes baseados nos filtros de data.
    *   **Visualização de Tabela Resumida:** Tabela compacta na tela mostrando uma prévia de 5 linhas dos dados.
    *   **Botões de Download:** Botões visíveis e destacados para download de arquivos nos formatos **PDF** ou **CSV / Excel** contendo os dados consolidados.

---

## ⚙️ 4. Diretrizes de Comportamento dos Elementos de Interface

Para garantir uma boa experiência de uso (UX), o designer deve atentar-se aos seguintes estados de interface:

1.  **Estados dos Botões:**
    *   *Default (Normal):* Cor sólida ou outline bem definido.
    *   *Hover (Passar o mouse):* Transição suave de cor ou brilho neon na borda.
    *   *Disabled (Desabilitado):* Transparência de 50%, cursor não clicável. Utilizado quando faltam seleções obrigatórias no formulário de round.
    *   *Loading (Carregando):* Spinner substituindo o texto ao salvar dados ou gerar partidas para evitar cliques duplicados.
2.  **Alertas e Feedbacks Visuais (Toasts/Flash Messages):**
    *   Avisos de sucesso (placar salvo, check-in realizado) em fundo verde escuro com borda verde brilhante.
    *   Avisos de perigo (W.O. iminente, erro de login) em fundo vermelho escuro com borda vermelha brilhante.
3.  **Tabelas Responsivas:**
    *   Todas as tabelas de classificação e partidas devem permitir rolagem horizontal em telas pequenas de celulares, evitando quebrar a estrutura do layout.
    *   Ocultar colunas secundárias (ex: Assists ou Losses) em dispositivos móveis, mantendo apenas informações cruciais (Nick, K/D, Placar).
4.  **Atualização Sem Recarregamento de Página (AJAX/Fetch):**
    *   O painel de controle de rounds do árbitro e as estatísticas da súmula pública atualizam de forma assíncrona. A interface não deve piscar ou dar "F5" ao confirmar um round, o placar e o feed devem ser atualizados instantaneamente por manipulação direta do DOM.
