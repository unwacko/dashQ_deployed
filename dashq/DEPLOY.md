# Deploying dashQ to Azure, step by step

Run every command in **Terminal**, one at a time. Wait for each to finish before the next.
Lines starting with `#` are notes, not commands.

## Step 1. Go to the project folder

```bash
cd "/Users/main/Everything/Programming/vibecoding prac/dash-Q/dashq"
```

## Step 2. Sign in to Azure again

Your university account needs a fresh sign-in with multi-factor authentication.

```bash
az logout
```

```bash
az login --tenant "81f8828b-91d6-4241-9739-765659c3bd22" --scope "https://management.core.windows.net//.default"
```

A browser window opens. Sign in with your college account and approve the MFA prompt.
If the terminal asks you to pick a subscription, pick **Azure for Students**.

Check it worked. It should say `Azure for Students` and `Enabled`:

```bash
az account show --query "{name:name, state:state}" -o table
```

## Step 3. Pick your app name

This becomes your address: `https://<name>.azurewebsites.net`. The QR codes point there, so choose
something you'll keep. Lowercase letters, numbers and dashes only. Replace `dashq-app` if you want another name:

```bash
NAME=dashq-app
```

```bash
GROUP=dashq-rg
```

```bash
REGION=centralindia
```

## Step 4. Create the resource group, the free plan and the web app

```bash
az group create --name $GROUP --location $REGION
```

```bash
az appservice plan create --name dashq-plan --resource-group $GROUP --sku F1 --is-linux --location $REGION
```

```bash
az webapp create --name $NAME --resource-group $GROUP --plan dashq-plan --runtime "PYTHON:3.12"
```

- If you get **"name already taken"**, go back to Step 3, pick another name and run only the last command again.
- If the region is **refused** (student subscriptions limit regions), delete the group with
  `az group delete --name $GROUP --yes`, then run `REGION=southindia` (or `southeastasia`) and redo Step 4.

## Step 5. Tell Azure how to start the app

```bash
az webapp config set --name $NAME --resource-group $GROUP --startup-file 'gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 120 "app:create_app()"'
```

```bash
az webapp update --name $NAME --resource-group $GROUP --https-only true
```

## Step 6. Set the secrets

The `SECRET_KEY` is made randomly inside this command and never printed:

```bash
az webapp config appsettings set --name $NAME --resource-group $GROUP --output none --settings SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')" DATA_DIR=/home/data DASHQ_TZ=Asia/Kolkata SCM_DO_BUILD_DURING_DEPLOYMENT=true
```

## Step 7. Make the upload package

This zips only the app. It leaves out `.venv`, the tests and your local `data/` folder (your test accounts):

```bash
rm -f ../dashq-deploy.zip && zip -r -q ../dashq-deploy.zip app.py config.py db.py auth.py schema.sql requirements.txt README.md sections services templates static -x "*/__pycache__/*" "*.pyc" "*.DS_Store"
```

## Step 8. Upload it

This takes 3 to 8 minutes, because Azure installs pandas, matplotlib and the rest:

```bash
az webapp deploy --name $NAME --resource-group $GROUP --src-path ../dashq-deploy.zip --type zip
```

## Step 9. Open your site

```bash
open https://$NAME.azurewebsites.net
```

The first visit can take up to a minute while the free plan wakes up. Then check:

1. The landing page loads, with the dashQ look and the Inter font.
2. **Sign up** a test business. You land on the live board. Your customer page is `https://<name>.azurewebsites.net/b/<your-slug>`.
3. Open the customer page on your phone and join the line.
4. Optional: make the two sample businesses in the Kudu SSH console with `flask --app app:create_app seed-demo`.

## If something goes wrong

Watch the live server log (press Ctrl+C to stop watching):

```bash
az webapp log config --name $NAME --resource-group $GROUP --docker-container-logging filesystem
```

```bash
az webapp log tail --name $NAME --resource-group $GROUP
```

| You see | Do this |
|---|---|
| "Application Error" page | Look at the log. `Set a long random SECRET_KEY` means Step 6 didn't save, so run it again |
| `ModuleNotFoundError` in the log | `SCM_DO_BUILD_DURING_DEPLOYMENT` was missing. Run Step 6, then Step 8 again |
| `database is locked` or `disk I/O error` | Add the setting `DASHQ_JOURNAL_MODE=DELETE` (same command as Step 6, just that setting), then restart: `az webapp restart --name $NAME --resource-group $GROUP` |
| Very slow first load | Normal on the free F1 plan. It sleeps when nobody uses it |

## Later

- **Updating the site after changing code:** run Step 1, the `NAME=` and `GROUP=` lines from Step 3, then Steps 7 and 8.
- **Before a demo or real users:** move to B1 (about $13/month) and turn on Always On:
  `az appservice plan update --name dashq-plan --resource-group $GROUP --sku B1`, then
  `az webapp config set --name $NAME --resource-group $GROUP --always-on true`.
- **Budget alert:** in the Azure portal, open Cost Management → Budgets and add alerts at $30 and $70.
- **Backups:** open `https://<name>.scm.azurewebsites.net`, then Debug console → Bash, go to `/home/data`, and download `dashq.db`.
- **Never** turn on scale-out (more than one instance). SQLite only works on one server.
