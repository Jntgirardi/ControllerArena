# 🎮 Controller Arena — Como a Plataforma Irá Elevar o Nosso Campeonato

Olá! Este documento foi preparado especialmente para apresentar o **Controller Arena**, a plataforma web que vamos utilizar para gerenciar, automatizar e profissionalizar o nosso campeonato de e-Sports (focado em *CS2* e *Valorant*). 

Abaixo, explico de forma simples e direta como o sistema funciona, o que cada pessoa envolvida no evento vai ver na tela e como isso vai facilitar a nossa vida no dia a dia da competição.

---

## 🎯 1. O que o Controller Arena brings to the our championship?

Organizar torneios de e-Sports costuma dar muito trabalho manual: chaves feitas no papel ou em planilhas que atrasam, informações espalhadas em grupos de chat e a contagem de pontos que sempre gera dúvidas. 

O **Controller Arena** resolve tudo isso centralizando a operação em um único lugar:
* **Chaveamento Automático:** A chave do torneio (brackets estilo mata-mata) é gerada pelo sistema em apenas um clique.
* **Fim das Súmulas Manuais:** Os árbitros registram os pontos rodada por rodada em uma tela simples e o placar público atualiza na hora para quem estiver assistindo.
* **Estatísticas Completas (KDA):** O sistema calcula os abates, mortes e assistências de cada jogador, gerando engajamento para a comunidade.
* **Integração com o Discord:** O sistema avisa automaticamente no nosso servidor do Discord sempre que um confronto for gerado ou quando uma partida terminar.

---

## 👥 2. Quem faz o que no sistema? (Níveis de Acesso)

Para manter a organização do campeonato segura, dividimos quem pode acessar e alterar as informações em quatro perfis:

1. **Você e a Organização (ADMIN):** Tem controle total do campeonato. Vocês cadastram os times, geram os confrontos, escalam os árbitros e podem alterar qualquer informação se for necessário.
2. **Os Árbitros (REFEREE):** Possuem acesso a uma área exclusiva para lançar os resultados das partidas de forma rápida, rodada por rodada, direto do celular ou computador.
3. **O Público e Jogadores (VISITANTE):** Qualquer pessoa pode acessar o site para acompanhar a tabela de jogos ao vivo, ver as estatísticas dos jogadores e consultar os rankings. Os jogadores ficam cadastrados no sistema para acompanhar pontuações e estatísticas, mas não precisam criar login ou senha para jogar.

---

## 📺 3. Roteiro Prático de Telas (O que cada um vai ver)

Aqui está um "passeio" por cada tela do sistema e o que elas fazem:

### 🌐 O que o público e os jogadores vão ver (Área Pública)

#### Tela 1: A Página Inicial (Home HLTV-Style)
* **O que é:** O painel principal do evento. Tem um visual moderno, limpo e super fácil de navegar no celular.
* **O que ela mostra:**
  - Um destaque bem visível para as **Partidas Ao Vivo** (com uma marcação vermelha piscando "Ao Vivo"), exibindo o placar atualizado em tempo real.
  - A lista com as próximas partidas agendadas e os resultados dos jogos que já aconteceram.
  - Cards com os campeonatos ativos, mostrando o prêmio, o jogo e o número de times participantes.

#### Tela 2: A Árvore de Confrontos (Detalhes do Campeonato)
* **O que é:** Onde todos acompanham a evolução do campeonato.
* **O que ela mostra:**
  - A tabela visual do torneio (brackets) mostrando quem enfrenta quem nas Oitavas, Quartas, Semifinal e Final. As chaves avançam sozinhas conforme os jogos acabam.
  - A lista com o escudo e o nome de todos os times que estão participando.

#### Tela 3: A Súmula da Partida (Histórico do Jogo)
* **O que é:** A página detalhada de um confronto encerrado ou em andamento.
* **O que ela mostra:**
  - O placar gigante do jogo, o mapa que foi jogado e o campeonato.
  - O log das rodadas: uma linha do tempo mostrando exatamente como cada ponto foi conquistado (ex: *Rodada 1: Time A venceu desarmando a C4/Spike*; *Rodada 2: Time B venceu eliminando todos*).
  - A tabela de desempenho individual (KDA) dos jogadores de cada time.
  - O selo **MVP** (Destaque do Jogo): o sistema destaca automaticamente com uma medalha dourada o jogador que teve a melhor pontuação na partida.

#### Tela 4: O Ranking Geral da Liga (Leaderboard)
* **O que é:** O termômetro de quem está jogando melhor no campeonato.
* **O que ela mostra:**
  - Um pódio visual em 3D para os 3 melhores jogadores e times.
  - A tabela de classificação completa com o número de vitórias, derrotas, aproveitamento (%) e média de abates por morte (K/D).

---

### ⚖️ O que a equipe técnica vai usar (Área de Arbitragem)

#### Tela 5: Painel de Escala do Árbitro
* **O que é:** A agenda de trabalho do árbitro.
* **O que ela mostra:**
  - Uma lista simples com todas as partidas que a organização delegou para aquele árbitro.
  - Um botão vermelho **"Arbitrar"** ao lado das partidas que estão prontas para começar.

#### Tela 6: Controle da Partida em Tempo Real
* **O que é:** A ferramenta de trabalho do árbitro durante o jogo.
* **O que ela mostra:**
  - Dois botões grandes com o nome dos dois times. Quando um time faz um ponto, o árbitro clica no botão dele, escolhe como o ponto foi ganho (ex: *Eliminação*, *Tempo Esgotado*, etc.) e confirma. O placar atualiza na hora para o público.
  - Um feed das rodadas anteriores com um botão **"Desfazer"**. Se o árbitro lançar um ponto errado por engano, ele clica ali e o placar é corrigido imediatamente.
  - **Fechamento do Jogo (Inserir KDA):** Quando a partida acaba, abre-se uma tela simples onde o árbitro digita o número de abates, mortes e assistências de cada jogador para salvar a súmula final.

---

### ⚙️ O seu controle (Área da Organização / ADMIN)

#### Tela 7: Painel de Controle do Administrador (Dashboard)
* **O que é:** A sua visão geral da liga.
* **O que ela mostra:**
  - Resumos numéricos rápidos: quantos jogadores e times estão cadastrados e quantos campeonatos estão rodando.
  - Atalhos rápidos para criar um novo campeonato, cadastrar um time ou adicionar jogadores.

#### Tela 8: Formulários de Cadastro (CRUDs)
* **O que é:** Onde você alimenta o sistema com as informações do evento.
* **Como funciona:**
  - **Cadastro de Times:** Você insere o nome, a sigla (TAG), o jogo e faz o upload do escudo do time. O sistema ajusta a imagem automaticamente.
  - **Cadastro de Campeonatos:** Você define o nome do torneio, as datas, o jogo (CS2/Valorant), o número de vagas e insere o link do Discord para envio de avisos automáticos.
  - **Criador de Partidas:** Onde você monta os confrontos manuais (caso não queira usar a chave automática), escolhe o mapa da partida e escala qual árbitro vai apitar.

#### Tela 9: Central de Relatórios
* **O que é:** A ferramenta para extrair dados oficiais para patrocinadores.
* **O que ela faz:**
  - Permite filtrar os jogos por data e baixar relatórios completos das partidas, rankings ou logs de segurança em formato **PDF** (pronto para impressão/envio) ou **CSV** (para abrir no Excel).

---

## 🔄 4. Como o campeonato vai rodar na prática (Fluxo do Evento)

Para você visualizar o dia do evento, o campeonato vai seguir este fluxo simples dentro do sistema:

1. **Preparação:** Nós cadastramos os times e os jogadores participantes. Em seguida, criamos o campeonato no painel administrativo.
2. **Chaveamento:** Com os times definidos, clicamos em **"Gerar Confrontos"**. O sistema cria a chave mata-mata instantaneamente, define as partidas e envia um alerta automático no nosso Discord.
3. **Durante as Partidas:** Os árbitros entram no painel de arbitragem e lançam os pontos rodada por rodada. O público acompanha o placar ao vivo e a tabela de chaves atualizando de forma dinâmica pela página do evento.
4. **Fechamento:** O árbitro encerra o jogo, lança as estatísticas de KDA e o sistema define o MVP. O ranking geral da liga é recalculado automaticamente no mesmo segundo.
5. **Pós-Evento:** Nós extraímos o relatório em PDF com todas as estatísticas para divulgar aos times e apresentar para os parceiros do evento.

Com essa estrutura, garantimos um campeonato transparente, dinâmico e sem atrasos operacionais!
