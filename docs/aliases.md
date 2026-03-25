# Command Aliases

Aliases provide shorter routes to common operations. They resolve to identical dynamic commands and produce identical output.

| Alias | Expands To | Description |
|-------|-----------|-------------|
| `mws mail list` | `mws me messages list` | List messages in inbox |
| `mws mail get` | `mws me messages get` | Get a specific message |
| `mws mail send` | `mws me send-mail` | Send an email |
| `mws cal list` | `mws me calendar events list` | List calendar events |
| `mws cal create` | `mws me calendar events create` | Create a calendar event |
| `mws teams list` | `mws me joined-teams list` | List joined teams |
| `mws drive ls` | `mws me drive root children list` | List files in OneDrive root |
| `mws drive get` | `mws me drive root get` | Get a file from OneDrive |

## Usage

All flags work identically with aliases:

```bash
# These are equivalent:
mws mail list --top 5 --filter "isRead eq false"
mws me messages list --top 5 --filter "isRead eq false"
```

## Listing All Aliases

```bash
mws aliases list
```

Returns a JSON array of all available aliases with their expansions.
