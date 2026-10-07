# Publicar na nuvem (Google Cloud Run) e usar no celular de qualquer lugar

**Atalho:** no Cloud Shell, rode `./deploy.sh` (faz tudo abaixo).

Pré-requisitos: projeto Google Cloud com faturamento, `gcloud` instalado e logado, Earth Engine
registrado no projeto (https://code.earthengine.google.com/register).

```bash
export PROJ=seu-projeto-gcp
gcloud config set project $PROJ
gcloud services enable run.googleapis.com earthengine.googleapis.com firestore.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com secretmanager.googleapis.com

# 1. Banco do histórico
gcloud firestore databases create --location=southamerica-east1

# 2. Conta de serviço com acesso ao Earth Engine e ao Firestore
gcloud iam service-accounts create cachoeiras
SA=cachoeiras@$PROJ.iam.gserviceaccount.com
for R in roles/earthengine.writer roles/serviceusage.serviceUsageConsumer roles/datastore.user; do
  gcloud projects add-iam-policy-binding $PROJ --member=serviceAccount:$SA --role=$R
done
# Registre a conta $SA no Earth Engine: https://code.earthengine.google.com/register (aba "Service account")

# 3. Segredos (senha do site e, opcional, chave da IA)
printf 'SUA_SENHA' | gcloud secrets create app-senha --data-file=-
printf 'sk-ant-...' | gcloud secrets create anthropic-key --data-file=-
for S in app-senha anthropic-key; do
  gcloud secrets add-iam-policy-binding $S --member=serviceAccount:$SA --role=roles/secretmanager.secretAccessor
done

# 4. Publicar (dentro de cachoeiras/)
gcloud run deploy cachoeiras --source . --region southamerica-east1 --service-account $SA \
  --allow-unauthenticated --timeout 300 --max-instances 2 \
  --set-env-vars EE_PROJECT=$PROJ,GOOGLE_MAPS_API_KEY= \
  --set-secrets APP_PASSWORD=app-senha:latest,ANTHROPIC_API_KEY=anthropic-key:latest
```
O comando imprime uma URL `https://cachoeiras-xxxx.run.app`. Abra no celular: o navegador pede
uma senha (usuário em branco, senha = a que você definiu). Dá para "Adicionar à tela inicial".

- `--allow-unauthenticated` é seguro aqui porque a própria aplicação exige `APP_PASSWORD`.
- Sem `ANTHROPIC_API_KEY` a busca funciona só com a nota heurística.
- Para usar o mapa do Google, passe sua chave em `GOOGLE_MAPS_API_KEY` (restrinja-a ao domínio `*.run.app`).
- O histórico fica no Firestore e sobrevive a reinícios.
