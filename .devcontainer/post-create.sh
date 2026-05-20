#!/usr/bin/env bash
#
# Entry point for devcontainer.json's postCreateCommand. Consolidates what
# was previously a long `&&`-chained inline string. Benefits:
#
#   1. Output is tee'd to /tmp/post-create.log. Zed does not surface
#      postCreateCommand stdout/stderr anywhere in its UI, so the log is
#      the canonical place to diagnose first-boot failures.
#   2. Volume mount points are self-healed at runtime. The Dockerfile
#      pre-creates and chowns /home/vscode/.claude and /home/vscode/.config
#      subdirs, but fresh named volumes can mount as root:root depending on
#      Docker version, and image-time ownership does not always propagate.
#   3. Best-effort plugin pre-install so a fresh claude-state volume doesn't
#      leave declared plugins silently unresolved on first `claude` run.
#
# Rerun manually at any time to re-apply: `bash .devcontainer/post-create.sh`
# inside the container (e.g. after `docker volume rm`-ing one of the auth
# volumes).

set -euo pipefail

exec > >(tee -a /tmp/post-create.log) 2>&1
echo "=== post-create.sh starting at $(date -Iseconds) ==="

# ---------------------------------------------------------------------------
# Volume mount-point self-heal
# ---------------------------------------------------------------------------
# Named volumes (claude-state, gh-config, gcloud-config) can first-mount as
# root:root. sudo here is the passwordless grant from the Dockerfile's
# sudoers entry for vscode. The .keep files ensure each volume has at
# least one vscode-owned entry, which helps Docker propagate ownership on
# subsequent mounts.
sudo mkdir -p /home/vscode/.claude \
              /home/vscode/.config/gh \
              /home/vscode/.config/gcloud
sudo touch /home/vscode/.claude/.keep \
           /home/vscode/.config/gh/.keep \
           /home/vscode/.config/gcloud/.keep
sudo chown -R vscode:vscode /home/vscode/.claude /home/vscode/.config

# Persist ~/.claude.json across container rebuilds. Claude Code stores
# machine-wide state in this top-level file (separate from the ~/.claude/
# directory, which IS covered by the claude-state volume). Compose can't
# mount a named volume onto a single file, so symlink ~/.claude.json to a
# path inside the volume. Without this, every `docker rm -f` wipes the
# state file even though the credentials in ~/.claude/.credentials.json
# survive — which is why Claude prompts for login on every new container.
if [ ! -L /home/vscode/.claude.json ]; then
    # Preserve any existing real file contents (e.g. a session that
    # pre-dates this fix) by moving into the volume before replacing with
    # a symlink.
    if [ -f /home/vscode/.claude.json ]; then
        mv /home/vscode/.claude.json /home/vscode/.claude/.claude.json
    fi
    ln -sf /home/vscode/.claude/.claude.json /home/vscode/.claude.json
fi

# ---------------------------------------------------------------------------
# git plumbing
# ---------------------------------------------------------------------------
# safe.directory handles the UID-mismatch git reports when the repo is
# mounted from a host with a different owner. lfs install/pull happens
# here (not at image time) because it needs the bind-mounted repo.
WORKSPACE="${CONTAINER_WORKSPACE_FOLDER:-/workspaces/Equitable-Polling-Locations}"
git config --global --add safe.directory "$WORKSPACE"
git lfs install --local --force
git lfs pull

# ---------------------------------------------------------------------------
# gh credential helper
# ---------------------------------------------------------------------------
# If the gh-config volume already has a valid auth (from a previous
# container) wire gh up as git's HTTPS credential helper automatically.
# Otherwise leave a hint; the contributor runs `gh auth login` themselves
# in an interactive terminal and re-runs `gh auth setup-git` after.
if gh auth status >/dev/null 2>&1; then
    gh auth setup-git
else
    echo "gh not authenticated yet — run 'gh auth login' inside the container,"
    echo "then 'gh auth setup-git' to wire it as git's credential helper."
fi

# ---------------------------------------------------------------------------
# Claude Code marketplace + plugin pre-install
# ---------------------------------------------------------------------------
# A fresh claude-state volume has no marketplaces registered (not even
# claude-plugins-official — the default `enabledPlugins` entries in
# .claude/settings.json silently fail to resolve until a marketplace is
# added). Registering + installing here means the first `claude` run
# works out of the box.
#
# Best-effort: wrapped in a subshell with `|| echo …` so plugin-install
# failures (network hiccup, CLI change, etc.) do NOT block the rest of
# post-create from running. The declared plugins in settings.json remain,
# so contributors will just see the interactive prompt on first use
# instead of the pre-installed state.
(
    claude plugin marketplace add anthropics/claude-plugins-official \
        && claude plugin marketplace update \
        && claude plugin install \
            superpowers@claude-plugins-official \
            commit-commands@claude-plugins-official \
            pyright-lsp@claude-plugins-official
) || echo "WARNING: claude plugin pre-install incomplete. The plugins are still declared in .claude/settings.json, so Claude will prompt you on first use — there is no manual step required unless you want to investigate why the pre-install failed (check /tmp/post-create.log)."

# ---------------------------------------------------------------------------
# R package install (slow — runs last so it does not block anything above)
# ---------------------------------------------------------------------------
# Delegates to run_r_install.sh, which writes its own /tmp/r-install.log,
# drops a failure marker at ~/.r-install-failed on error, and always exits 0
# so a broken R library does not block container startup.
bash .devcontainer/run_r_install.sh

echo "=== post-create.sh complete at $(date -Iseconds) ==="
