#!/data/data/com.termux/files/usr/bin/bash
cd ~/governor_ai

# --- Step 1: Load environment variables ---
source .env
LOGFILE=~/governor_ai/update.log
REPO_URL="https://github.com/AiGOVERNOR/governor_ai.git"
TAG_DATE=$(date +"v%Y.%m.%d-%H:%M")

echo "----- $(date): Checking for updates -----" >> $LOGFILE

# --- Step 2: Ensure valid git repo ---
if [ ! -d .git ]; then
    echo "$(date): Not a git repo — initializing..." >> $LOGFILE
    git init
    git remote add origin $REPO_URL
    git fetch origin main >> $LOGFILE 2>&1
    git reset --hard origin/main >> $LOGFILE 2>&1
fi

# --- Step 3: Fetch latest from GitHub ---
git fetch origin main >> $LOGFILE 2>&1

LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
    echo "$(date): Update detected — pulling latest changes..." >> $LOGFILE
    pkill -f governor.py
    git reset --hard origin/main >> $LOGFILE 2>&1

    # --- Step 4: Integrity verification ---
    find . -type f -name "*.py" -exec sha256sum {} \; > checksums.current
    if [ ! -f checksums.manifest ]; then
        echo "$(date): Creating baseline checksum manifest..." >> $LOGFILE
        find . -type f -name "*.py" -exec sha256sum {} \; > checksums.manifest
    fi

    if diff checksums.manifest checksums.current >/dev/null; then
        echo "$(date): Integrity check passed." >> $LOGFILE
    else
        echo "$(date): Integrity mismatch detected — recovering..." >> $LOGFILE
        git reset --hard origin/main >> $LOGFILE 2>&1
        find . -type f -name "*.py" -exec sha256sum {} \; > checksums.manifest
    fi

    # --- Step 5: Restart AI core ---
    nohup python governor.py > ~/governor_ai/governor.log 2>&1 &
    echo "$(date): Governor AI restarted successfully." >> $LOGFILE

    # --- Step 6: Auto-commit and tag the new version ---
    git add -A
    git commit -m "Auto-update and verification at $(date)" >> $LOGFILE 2>&1
    git tag -a "$TAG_DATE" -m "Governor AI version $TAG_DATE" >> $LOGFILE 2>&1
    git push origin main --tags >> $LOGFILE 2>&1
    echo "$(date): Auto-pushed version $TAG_DATE to GitHub." >> $LOGFILE

else
    echo "$(date): No updates detected — system stable." >> $LOGFILE
fi

# --- Step 7: Optional GitHub Auto-Reporting ---
if [ -n "$GITHUB_TOKEN" ]; then
    curl -s -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -d "{\"title\":\"Governor Auto-Update\",\"body\":\"Governor AI updated and versioned as $TAG_DATE at $(date).\"}" \
        https://api.github.com/repos/AiGOVERNOR/governor_ai/issues >> $LOGFILE
    echo "$(date): GitHub report created for tag $TAG_DATE." >> $LOGFILE
fi
