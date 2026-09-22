# Checklist de Deploy na VPS (instrucao.md Fase 20)

Itens que só podem ser feitos por você, com acesso real à VPS — não posso executá-los.

## 1. Pré-requisitos
- [ ] Docker + Docker Compose instalados (`docker --version`, `docker compose version`)
- [ ] Firewall (`ufw` ou equivalente): liberar apenas 22 (SSH), 80/443 (dashboard), e nunca expor 5432 (Postgres) publicamente
- [ ] Relógio sincronizado (`timedatectl` / `chrony` ou `ntpd`) — instrucao.md §61 exige isso para chamadas assinadas da Binance
- [ ] Usuário não-root para rodar o Docker (opcional, mas recomendado)

## 2. Configuração
```bash
git clone <repo> && cd AdapterTrading
cp .env.example .env               # raiz — define POSTGRES_PASSWORD
cp .env.example backend/.env       # backend — credenciais Binance, TRADING_MODE, CONTROL_API_TOKEN
```
- [ ] `POSTGRES_PASSWORD` forte e único (raiz `.env`)
- [ ] `CONTROL_API_TOKEN` forte e único (`backend/.env`) — sem ele os endpoints de controle ficam bloqueados (503), por design
- [ ] `BINANCE_API_KEY`/`BINANCE_API_SECRET` da conta real, com **withdrawal desabilitado** (confirmar no painel Binance — ver achado da Fase 2)
- [ ] IP da VPS cadastrado na whitelist da API key da Binance, se disponível
- [ ] `TRADING_MODE=paper` até você decidir explicitamente mudar para `live`

## 3. Subir os containers
```bash
docker compose up -d --build
docker compose exec backend-api alembic upgrade head   # cria as tabelas — NUNCA testado contra Postgres real ainda
docker compose logs -f backend-api worker-execution worker-market-data
```

## 4. Verificação
- [ ] `curl http://<vps-ip>/health` responde `{"status":"ok",...}`
- [ ] `curl http://<vps-ip>/status` responde com `bot_state`
- [ ] Dashboard acessível em `http://<vps-ip>/`
- [ ] `worker-market-data` está coletando candles reais (Fase 21 — ativado automaticamente ao subir o container; confirme via logs ou consultando a tabela `market_data`)
- [ ] `worker-execution` reconciliou com sucesso no startup (procure `worker_execution_startup` nos logs, `reconciled: true`)

## 5. Backups (instrucao.md §110)
- [ ] Rotina de backup do volume `postgres_data` (ex.: `pg_dump` agendado via cron, ou snapshot do volume Docker)
- [ ] Backups incluem: orders, fills, positions, ledger_entries, signals, order_intents — tudo já está no mesmo banco Postgres, então um backup completo do banco cobre isso

## 6. TLS (produção real)
- [ ] Certificado (ex. Let's Encrypt via certbot) na frente do dashboard/API se for exposto além do IP puro — não incluído neste `docker-compose.yml` (Traefik/Nginx com TLS fica a seu critério de configuração de domínio)

## Bloqueios conhecidos que precisam da sua ação
1. `alembic upgrade head` nunca rodou contra um Postgres real — as migrations foram escritas à mão (sem Postgres disponível durante o desenvolvimento) e só testadas contra SQLite. É essencial confirmar que rodam sem erro na VPS.
2. `can_withdraw: True` na API key da Binance (achado da Fase 2) — ainda não resolvido, até onde sei.
3. Nenhuma ordem real foi enviada ainda pelo sistema automatizado — o script `backend/scripts/place_real_test_order.py` continua a forma recomendada de validar o fluxo de execução manualmente antes de deixar o `worker-execution` operando sozinho.
