# Azure AD App Registration for mws

## Prerequisites

- An Azure AD tenant (any Microsoft 365 subscription)
- Global Admin or Application Administrator role

## Step 1: Register the App

1. Go to [Azure Portal](https://portal.azure.com) → Azure Active Directory → App registrations
2. Click **New registration**
3. Name: `mws-cli` (or any name you prefer)
4. Supported account types: **Accounts in this organizational directory only** (single tenant)
5. Redirect URI: leave blank (device code flow doesn't need one)
6. Click **Register**

## Step 2: Note the IDs

From the app's Overview page, copy:
- **Application (client) ID** → use as `--client-id` or `MWS_CLIENT_ID`
- **Directory (tenant) ID** → use as `--tenant-id` or `MWS_TENANT_ID`

## Step 3: Configure API Permissions

Go to **API permissions** → **Add a permission** → **Microsoft Graph** → **Delegated permissions**.

Add the scopes you need:

| Service | Scopes |
|---------|--------|
| Mail | `Mail.Read`, `Mail.Send`, `Mail.ReadWrite` |
| Calendar | `Calendars.Read`, `Calendars.ReadWrite` |
| Teams | `Team.ReadBasic.All`, `ChannelMessage.Read.All`, `Chat.Read` |
| Drive | `Files.Read.All`, `Files.ReadWrite.All` |
| User | `User.Read` (always needed) |

Click **Grant admin consent** if you have admin rights.

## Step 4: Enable Device Code Flow

Go to **Authentication** → under **Advanced settings**, set **Allow public client flows** to **Yes**.

## Step 5: Authenticate

```bash
mws auth login --tenant-id <your-tenant-id> --client-id <your-client-id>
```

Follow the device code instructions printed to stderr.

## Client Credentials (Service Principal)

For unattended scripts, use client credentials instead:

1. Go to **Certificates & secrets** → **New client secret**
2. Copy the secret value
3. Set environment variables:

```bash
export MWS_TENANT_ID=<tenant-id>
export MWS_CLIENT_ID=<client-id>
export MWS_CLIENT_SECRET=<secret-value>
```

Note: Client credentials use **Application permissions**, not Delegated. Add the `.ReadWrite.All` variants under Application permissions and grant admin consent.
