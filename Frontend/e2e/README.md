# End-to-end check

Runs the app in a real browser against a throwaway backend (its own database, no Supabase, Discord or WhatsApp):

```
cd Frontend && VITE_API_URL=http://localhost:8012 npm run build
cd ../Backend && ENGANO_DB_PATH=/tmp/e2e.db SUPABASE_URL= SUPABASE_DB_URL= SUPABASE_SECRET_KEY= DISCORD_BOT_TOKEN= WHATSAPP_ACCESS_TOKEN= \
  AI_PROVIDER=rules_only ENGANO_POLICY_SOURCE=fixture ENGANO_BRAND_ID=nimbus_cloud ENGANO_CORS_ORIGINS=http://localhost:4175 \
  PYTHONPATH=..:. ../.venv/bin/python -m uvicorn main:app --port 8012 &
cd ../Frontend && npx vite preview --port 4175 --strictPort &
npm run e2e
```
