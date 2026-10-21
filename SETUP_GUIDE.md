# Industria-AI setup guide

Do Part 1 to get the app running. Parts 2 and 3 are optional and can be done
any time later: sign-in and history switch on by themselves once their keys
are added, with no code changes.

---

## Part 1: Deploy the app (required, about 10 minutes)

### 1.1 Update GitHub
1. Unzip `industria-ai.zip`.
2. Open your repository on GitHub, click **Add file → Upload files**.
3. Drag in **everything inside** the unzipped `industria-ai` folder, including the
   hidden `.streamlit` folder (on Windows, turn on *View → Hidden items*; on Mac,
   press `Cmd + Shift + .` in Finder).
4. Click **Commit changes**.
5. These old files are no longer used. Delete any that are still in your repo
   (open the file, click **...**, **Delete file**, **Commit changes**):
   `utils/retry.py`, `utils/litellm_patch.py`, `utils/context_builder.py`, `utils/state.py`.
   They are harmless if left, but deleting keeps the repo clean.

> Never upload a file called `secrets.toml`. Only `secrets.toml.example` belongs on GitHub.

### 1.2 Deploy on Streamlit Community Cloud
If your app is already deployed on **Python 3.11, 3.12 or 3.13**, it redeploys by
itself after the commit; skip to 1.3.

For a new app: **share.streamlit.io → Create app** → choose the repo, branch `main`,
file `app.py` → **Advanced settings** → **Python version: 3.12** (never 3.14) → Deploy.

### 1.3 Secrets
App → **⋮ → Settings → Secrets**, paste and fill in:

```toml
GROQ_API_KEY = "gsk_..."
SERPER_API_KEY = "..."
OPENALEX_API_KEY = "..."
```

Click **Save**. The app restarts within a minute.

### 1.4 Test
Run one analysis in two-step mode and one in one-step mode. In the final review,
open **Full analysis → Tools used by the agents** and check that
`evidence_search` and `scholarly_search` show `ok`.

---

## Part 2: Sign in with Google (optional, about 15 minutes)

Lets testers sign in so their analyses are saved. Guests can still use the app.

### 2.1 Create the Google sign-in client
1. Go to **console.cloud.google.com** and sign in.
2. Top bar → project picker → **New project** → name it `Industria-AI` → **Create**, then select it.
3. Search for **Google Auth Platform** and open it → **Get started**.
   - App name: `Industria-AI`; support email: yours → **Next**.
   - Audience: **External** → **Next**.
   - Contact email: yours → **Next** → agree → **Create**.
4. Left menu **Audience** → **Publish app** → **Confirm**.
   (Without this, only accounts you list as test users can sign in. The app asks
   only for name and email, so publishing needs no Google review.)
5. Left menu **Clients** → **Create client**:
   - Application type: **Web application**; name: `Industria-AI web`.
   - **Authorized redirect URIs → Add URI**:
     `https://YOUR-APP-NAME.streamlit.app/oauth2callback`
     (use your app's exact address, ending in `/oauth2callback`).
   - **Create**. Copy the **Client ID** and **Client secret**.

### 2.2 Add to Streamlit Secrets
Add this block at the **end** of your secrets (sections must come after the plain keys):

```toml
[auth]
redirect_uri = "https://YOUR-APP-NAME.streamlit.app/oauth2callback"
cookie_secret = "PASTE-A-LONG-RANDOM-STRING-HERE"
client_id = "....apps.googleusercontent.com"
client_secret = "GOCSPX-..."
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
```

For `cookie_secret`, type any long random string of 32+ characters (letters and numbers).

Save. A **Sign in with Google** button appears top right.

---

## Part 3: History and feedback storage with Supabase (optional, about 10 minutes)

Without this, feedback is kept only until the app restarts, and history is off.

1. Go to **supabase.com** → **Start your project** → sign in with GitHub.
2. **New project**: name `industria-ai`, set a database password (save it),
   region closest to your users → **Create new project**. Wait about 2 minutes.
3. Left menu **SQL Editor** → **New query** → paste the contents of
   `supabase_setup.sql` from the repo → **Run**. You should see "Success".
4. Left menu **Project Settings → API Keys**: copy the **Secret key**
   (starts with `sb_secret_`; on older projects, the `service_role` key).
5. **Project Settings → Data API** (or **API**): copy the **Project URL**.
6. Add to Streamlit Secrets, **above** the `[auth]` block:

```toml
SUPABASE_URL = "https://xxxxxxxx.supabase.co"
SUPABASE_KEY = "sb_secret_..."
```

Save. Signed-in users now get **My history** in the sidebar, and all feedback is
stored. To read feedback: Supabase → **Table Editor → feedback** (you can export
it as CSV).

> The secret key gives full database access. Keep it only in Streamlit Secrets.
> Free Supabase projects pause after a week with no activity; open the project
> dashboard and click **Restore** if that happens.

---

## Troubleshooting

| What you see | Fix |
|---|---|
| `ConfigError` mentioning pydantic on start | The app is on Python 3.14. Delete and redeploy with Python 3.12. |
| "GROQ_API_KEY is missing" | Add it in Secrets and save. |
| Yellow banner: daily limit reached | Normal on the free Groq plan. The app switches to the backup model automatically; limits reset at midnight UTC (5:00 am Pakistan time). |
| Users see "Add your own free Groq key" | Your shared key used both models' daily allowance. Users can paste their own free key to continue, or wait for the reset at midnight UTC. Upgrading your Groq account to the Developer tier removes the daily cap. |
| Analysis takes several minutes | The free Groq plan allows 8,000 tokens per minute per model, so calls queue briefly. Groq's paid Developer tier removes this. |
| Google says `redirect_uri_mismatch` | The redirect URI in Google and in Secrets must match exactly, including `https` and `/oauth2callback`. |
| Google says the app is in testing / access blocked | Google Auth Platform → Audience → **Publish app**. |
| "Couldn't save to history" | Check `SUPABASE_URL` and `SUPABASE_KEY`, and that `supabase_setup.sql` was run. |
| Secrets error after editing | Plain keys (`GROQ_API_KEY = ...`) must be above the `[auth]` block. |
