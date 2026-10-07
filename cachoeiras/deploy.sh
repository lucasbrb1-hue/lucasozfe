#!/usr/bin/env bash
# Publica o rastreador no Cloud Run. Rode no Cloud Shell, dentro de cachoeiras/.
set -euo pipefail
PROJ="$(gcloud config get-value project 2>/dev/null)"
[ -n "$PROJ" ] || { echo "Defina o projeto: gcloud config set project ID_DO_PROJETO"; exit 1; }
REGIAO=southamerica-east1
SA_NOME=cachoeiras
SA="$SA_NOME@$PROJ.iam.gserviceaccount.com"

read -rsp "Escolha uma SENHA para o site: " SENHA; echo
read -rsp "Chave da API Anthropic (opcional, Enter para pular): " CHAVE_IA; echo

echo ">> Ativando serviços..."
gcloud services enable run.googleapis.com earthengine.googleapis.com firestore.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

echo ">> Banco do histórico (Firestore)..."
gcloud firestore databases create --location=$REGIAO 2>/dev/null || echo "(já existe)"

echo ">> Conta de serviço..."
gcloud iam service-accounts create $SA_NOME 2>/dev/null || echo "(já existe)"
for R in roles/earthengine.writer roles/serviceusage.serviceUsageConsumer roles/datastore.user; do
  gcloud projects add-iam-policy-binding "$PROJ" --member="serviceAccount:$SA" --role=$R --condition=None >/dev/null
done

echo ">> Segredos..."
segredo() {  # nome valor
  if gcloud secrets describe "$1" >/dev/null 2>&1; then
    printf '%s' "$2" | gcloud secrets versions add "$1" --data-file=- >/dev/null
  else
    printf '%s' "$2" | gcloud secrets create "$1" --data-file=- >/dev/null
  fi
  gcloud secrets add-iam-policy-binding "$1" --member="serviceAccount:$SA" \
    --role=roles/secretmanager.secretAccessor >/dev/null
}
segredo app-senha "$SENHA"
SEGREDOS="APP_PASSWORD=app-senha:latest"
if [ -n "$CHAVE_IA" ]; then segredo anthropic-key "$CHAVE_IA"; SEGREDOS="$SEGREDOS,ANTHROPIC_API_KEY=anthropic-key:latest"; fi

echo ">> Publicando (leva alguns minutos)..."
gcloud run deploy cachoeiras --source . --region $REGIAO --service-account "$SA" \
  --allow-unauthenticated --timeout 300 --max-instances 2 \
  --set-env-vars "EE_PROJECT=$PROJ" --set-secrets "$SEGREDOS"

cat <<MSG

======================================================
PRONTO. Falta UM passo manual (só na primeira vez):
registrar a conta de serviço no Earth Engine:
  https://code.earthengine.google.com/register
  -> escolha "Service account" e informe: $SA
Depois abra a URL impressa acima no celular
(usuário em branco, senha = a que você escolheu).
======================================================
MSG
