# Azure AD App Registration for mws

This guide walks through creating the Azure app registration required for `mws` to authenticate against Microsoft Graph API. You'll need to do this once; after that, `mws auth login` handles token acquisition and refresh automatically.

## Prerequisites

- A Microsoft 365 subscription (any tier — including E3/E5, Business, or even a free developer tenant from the [Microsoft 365 Developer Program](https://developer.microsoft.com/en-us/microsoft-365/dev-program))
- Permission to register applications in your tenant (Global Admin, Application Administrator, or Cloud Application Administrator role — or "Users can register applications" enabled in tenant settings)

## Step 1: Register the App

1. Go to the [Azure Portal](https://portal.azure.com)
2. Search for **"Microsoft Entra ID"** in the top search bar (formerly Azure Active Directory)
3. In the left sidebar, click **App registrations**
4. Click **+ New registration**
5. Fill in:
   - **Name:** `mws-cli` (or any name you prefer — this is just a display name)
   - **Supported account types:** Select **"Accounts in this organizational directory only"** (single tenant)
   - **Redirect URI:** Leave blank — device code flow doesn't require one
6. Click **Register**

You'll be taken to the app's overview page.

## Step 2: Copy Your IDs

From the app's **Overview** page, copy these two values — you'll need them to authenticate:

| Field | Where it's used |
|---|---|
| **Application (client) ID** | `--client-id` flag or `MWS_CLIENT_ID` env var |
| **Directory (tenant) ID** | `--tenant-id` flag or `MWS_TENANT_ID` env var |

## Step 3: Enable Device Code Flow

This is the step most people forget:

1. In the left sidebar, click **Authentication**
2. Scroll to **Advanced settings**
3. Set **"Allow public client flows"** to **Yes**
4. Click **Save**

Without this, `mws auth login` will fail with an "unauthorized_client" error.

## Step 4: Configure API Permissions

1. In the left sidebar, click **API permissions**
2. Click **+ Add a permission**
3. Select **Microsoft Graph**
4. Select **Delegated permissions**
5. Add the scopes you need:

| Service | Scopes | What they enable |
|---|---|---|
| **User** | `User.Read` | Always required — reads your own profile |
| **Mail** | `Mail.Read`, `Mail.Send`, `Mail.ReadWrite` | Read, send, and manage email |
| **Calendar** | `Calendars.Read`, `Calendars.ReadWrite` | Read and manage calendar events |
| **Teams** | `Team.ReadBasic.All`, `ChannelMessage.Read.All`, `Chat.Read` | Read teams, channels, and chat messages |
| **Drive** | `Files.Read.All`, `Files.ReadWrite.All` | Read and manage OneDrive/SharePoint files |

Start with `User.Read` plus the scopes for the services you actually need. You can always add more later.

6. If you have admin rights, click **Grant admin consent for [your tenant]**. If not, ask your tenant admin — some scopes (like `ChannelMessage.Read.All`) require admin consent.

## Step 5: Authenticate

```bash
mws auth login --tenant-id <your-tenant-id> --client-id <your-client-id>
```

This starts the device code flow:
1. `mws` prints a URL and a code to stderr
2. Open the URL in a browser, enter the code, and sign in
3. `mws` receives the token and stores it locally at `~/.config/mws/`

After the first login, tokens are cached and refreshed automatically. You shouldn't need to log in again unless your refresh token expires (typically 90 days).

## Verify It Works

```bash
# Check auth status
mws auth status

# Try a simple query
mws me get --select "displayName,mail"

# Dry-run to see what would be sent without actually calling the API
mws me messages list --top 5 --dry-run
```

---

## Client Credentials (Service Principal)

For unattended scripts, CI pipelines, or server-to-server scenarios, use client credentials instead of device code flow:

### Create a client secret

1. In your app registration, go to **Certificates & secrets**
2. Click **+ New client secret**
3. Add a description and choose an expiration
4. Click **Add** and **immediately copy the secret value** — it won't be shown again

### Configure application permissions

Client credentials use **Application permissions** (not Delegated). Go to **API permissions** → **Add a permission** → **Microsoft Graph** → **Application permissions** and add the scopes you need (typically the `.ReadWrite.All` variants). Grant admin consent.

### Set environment variables

```bash
export MWS_TENANT_ID=<tenant-id>
export MWS_CLIENT_ID=<client-id>
export MWS_CLIENT_SECRET=<secret-value>
```

When these are set, `mws` uses client credentials automatically — no `auth login` needed.

---

## Multiple Profiles

`mws` supports multiple auth profiles for different tenants or accounts:

```bash
# Login with a named profile
mws auth login --tenant-id <id> --client-id <id> --profile work

# Switch active profile
mws auth switch --profile work

# Use a profile for a single command
mws me messages list --profile work --top 5
```

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `unauthorized_client` | Device code flow not enabled | Step 3: set "Allow public client flows" to Yes |
| `AADSTS65001: The user or administrator has not consented` | Missing admin consent | Click "Grant admin consent" in API permissions |
| `No profile configured` | Haven't logged in yet | Run `mws auth login --tenant-id ... --client-id ...` |
| `invalid_client` (with client credentials) | Wrong secret or expired | Create a new client secret in Certificates & secrets |
