# Guia de Contribuição

Bem-vindo(a) ao repositório da Controller Arena! Este guia define o fluxo de trabalho com Git e GitHub para manter a `main` sempre estável e o histórico limpo.

## Fluxo de Branches

```
feature/xxx ──┐
fix/yyy    ───┼─▶ develop (testes/integração) ──▶ main (produção)
chore/zzz  ───┘
```

| Branch   | Papel                                              | Regra principal                          |
| :------- | :------------------------------------------------- | :--------------------------------------- |
| `main`   | Última versão estável (produção).                  | **Nunca commitar direto.** Só via PR.    |
| `develop`| Integração e testes. Branch padrão do repositório. | Recebe PRs de branches de trabalho.      |
| `feature/*`, `fix/*`, `chore/*` | Trabalho do dia a dia.                | Nascer da `develop` e voltar pra `develop`. |

## Regras Obrigatórias

1. **Nunca faça `git push` direto na `main`.**
   A `main` está protegida no GitHub: push direto, force-push e deleção são bloqueados até para administradores (`enforce_admins`). Qualquer mudança precisa passar por Pull Request.

2. **Sempre crie uma branch a partir da `develop`:**
   ```bash
   git checkout develop
   git pull origin develop
   git checkout -b feature/nome-da-tarefa
   ```

3. **Desenvolva, commite e suba a branch:**
   ```bash
   git add .
   git commit -m "feat: descreve a mudanca"
   git push -u origin feature/nome-da-tarefa
   ```

4. **Abra um Pull Request para a `develop`** (é a branch padrão do repo). Descreva o que foi feito e, se possível, cole o resultado dos testes.

5. **A integração `develop` → `main` é automática.** A GitHub Action `auto-merge-develop` roda os testes a cada push na `develop`; se passarem, abre e mergea sozinha o PR de `develop` → `main`. Você não precisa fazer nada manualmente.

## Padrão de Commits

Use mensagens curtas e claras no formato convencional:

- `feat: ...` — nova funcionalidade
- `fix: ...` — correção de bug
- `refactor: ...` — mudança que não altera comportamento
- `chore: ...` — tarefas gerais (deploy, deps, etc.)
- `docs: ...` — documentação
- `security: ...` — correções de segurança
- `clean: ...` — remoção de código morto

## Antes de Abrir um PR

1. Rode a suíte de testes:
   ```bash
   python -m pytest
   ```
2. Confirme que seu branch está atualizado com a `develop`:
   ```bash
   git fetch origin
   git merge origin/develop
   ```

## Resumo

**Nunca subir direto pra `main`.** O fluxo é:

```
feature/xxx -> develop (via PR) -> main (auto via GitHub Action)
```

Basta trabalhar em uma branch, abrir PR para a `develop` e mergear. A Action cuida do resto.
