---
name: mws-drive
description: "mws CLI: Manage OneDrive files — list, upload, download, and share."
metadata:
  version: 0.1.0
  openclaw:
    category: "productivity"
    requires:
      bins:
        - mws
    cliHelp: "mws schema show /me/drive"
---

# mws — Drive (OneDrive)

> PREREQUISITE: Read ../mws-shared/SKILL.md for auth setup and global flags.

## Required Scopes

`Files.Read.All`, `Files.ReadWrite.All`

## Key Commands

```bash
# List files in root
mws drive ls

# List files in a folder
mws me drive root children list --select "id,name,size,lastModifiedDateTime"

# Get file metadata
mws me drive items get --params '{"driveItem-id": "<ITEM_ID>"}'

# Create a folder
mws me drive root children create --body '{"name": "New Folder", "folder": {}}'

# Search for files
mws me drive search --params '{"q": "quarterly report"}'
```

## Recipes

### 1. List recent files

```bash
mws drive ls --select "name,size,lastModifiedDateTime" --top 20 --format table
```

### 2. Get file download URL

```bash
mws me drive items get --params '{"driveItem-id": "<ID>"}' --select "name,@microsoft.graph.downloadUrl"
```

### 3. Create a text file

```bash
mws me drive root children create --body '{"name": "notes.txt", "file": {}}'
```

## Tips

- OneDrive items use `driveItem-id` as the path parameter
- Use `--select` to include only needed fields — file metadata can be large
- For files >4MB, use chunked upload sessions (not yet supported in mws 0.1.0)
- Use `--dry-run` before any write operations
