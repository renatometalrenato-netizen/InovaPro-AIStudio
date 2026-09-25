# InovaPro v7 — sincronização automática de provedores

Branch segura de preparação: `deploy/mobile-v7-auto-sync`.

## Objetivo

Ativar o fluxo automático:

Instagram autorizado → Windsor.ai → normalização InovaPro → metric_snapshots → Dashboard → Diagnóstico 360° → Teste NOVA → detecção de resultado.

## Segurança operacional

- O pacote do backend é dividido em 6 partes e reconstruído no boot.
- O boot valida SHA-256 do ZIP antes de extrair.
- Nenhuma chave é armazenada no GitHub.
- O scheduler fica desligado por padrão.
- Mongo lock evita sincronização duplicada entre réplicas.

## Variáveis de produção

- `ENABLE_PROVIDER_SCHEDULER=false` durante validação inicial.
- `PROVIDER_SYNC_INTERVAL_MINUTES=360`.
- `WINDSOR_API_KEY` deve ser criada diretamente no Railway/secret store; não deve ser enviada em chat.
- `GEMINI_API_KEY` existente é mapeada em runtime para `GOOGLE_API_KEY` quando necessário.

## Ativação

1. Publicar v7 com scheduler desligado.
2. Validar `/api/health`, autenticação e NOVA.
3. Configurar `WINDSOR_API_KEY` diretamente no Railway.
4. Marcar as conexões Instagram elegíveis com `sync_driver=windsor` ou `provider_metadata.windsor_account_id`.
5. Ativar `ENABLE_PROVIDER_SCHEDULER=true`.
6. Conferir logs e `provider_sync_runs`.

O scheduler nunca inventa dados: se Windsor não estiver configurado, retorna `not_configured`.
