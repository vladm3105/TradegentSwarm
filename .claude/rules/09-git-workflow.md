# Git Workflow

## SSH Authentication

Remote is configured as:
```bash
git remote set-url origin git@github.com:vladm3105/TradegentSwarm.git
```

## Conda/OpenSSL Issue

If using conda, its `LD_LIBRARY_PATH` loads a newer OpenSSL that conflicts with system SSH.

**Fix options:**

```bash
# Option 1: Clear LD_LIBRARY_PATH for SSH (recommended)
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push

# Option 2: Use git alias (one-time setup)
git config --global alias.pushs '!GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push'
# Then use: git pushs

# Option 3: Deactivate conda
conda deactivate
git push
```

## Standard Workflow

```bash
git add -A
git commit -m "description of change"
GIT_SSH_COMMAND="LD_LIBRARY_PATH= /usr/bin/ssh" git push
```

## SSH Configuration

Requires `~/.ssh/config` entry:

```text
Host github.com
    HostName github.com
    User git
    IdentityFile ~/.ssh/your-github-key
    IdentitiesOnly yes
```

## Alternative: GitHub MCP

Use `github-vl` MCP server to avoid SSH issues:

```yaml
Tool: mcp__github-vl__push_files
Parameters:
  owner: vladm3105
  repo: TradegentSwarm
  branch: main
  files: [{path: "...", content: "..."}]
  message: "Add feature"
```
