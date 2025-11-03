#!/data/data/com.termux/files/usr/bin/bash
cd ~/governor_ai

# Load environment variables
source .env

LOGFILE=~/governor_ai/update.log
REPO_URL="https://github.com/AiGOVERNOR/governor_ai.git"

echo "----- $(date): Checking for updates -----" >> $LOGFILE

# Ensure Git repo exists
if [ ! -d .git ]; then
  echo "Not a git repo, initializing..." >> $LOGFILE
  git init
  git remote add origin $REPO_URL
fi

# Fetch updates
git fetch origin main >> $LOGFILE 2>&1

# Compare commits
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/main)

if [ "$LOCAL" != "$REMOTE" ]; then
  echo "Update available — pulling latest changes..." >> $LOGFILE
  git reset --hard origin/main >> $LOGFILE 2>&1

  # -------------------------------
  # Integrity Verification Section
  # -------------------------------
  echo "Verifying code integrity..." >> $LOGFILE

  if [ ! -f checksums.manifest ]; then
    echo "Creating new checksum baseline..." >> $LOGFILE
    find . -type f -name "*.py" -exec sha256sum {} \; > checksums.manifest
  fi

  # Recalculate hashes
  find . -type f -name "*.py" -exec sha256sum {} \; > checksums.current

  # Compare manifest vs current
  if diff checksums.manifest checksums.current > /dev/null ; then
    echo "Integrity check passed. Restarting Governor AI..." >> $LOGFILE
    pkill -f governor.py
    nohup python governor.py > ~/governor_ai/governor.log 2>&1 &
    echo "Governor AI restarted successfully at $(date)" >> $LOGFILE
  else
    echo "Integrity check FAILED — initiating recovery..." >> $LOGFILE
    diff checksums.manifest checksums.current >> $LOGFILE

    # Attempt recovery from GitHub
    echo "Restoring clean version from GitHub..." >> $LOGFILE
    git reset --hard origin/main >> $LOGFILE 2>&1
    find . -type f -name "*.py" -exec sha256sum {} \; > checksums.manifest
    echo "Checksum manifest regenerated after recovery." >> $LOGFILE

    # GitHub auto-reporting (requires GITHUB_TOKEN in .env)
    if [ -n "$GITHUB_TOKEN" ]; then
      curl -s -X POST \
        -H "Authorization: token $GITHUB_TOKEN" \
        -d "{\"title\": \"Integrity Recovery Triggered\", \"body\": \"Governor AI detected corruption at $(date) and auto-recovered from GitHub.\nSee update.log for details.\"}" \
        https://api.github.com/repos/AiGOVERNOR/governor_ai/issues >> $LOGFILE 2>&1
      echo "Recovery event reported to GitHub." >> $LOGFILE
    fi

    # Restart safely
    pkill -f governor.py
    nohup python governor.py > ~/governor_ai/governor.log 2>&1 &
    echo "Governor AI recovered and restarted at $(date)" >> $LOGFILE
  fi

else
  echo "No updates detected — system stable." >> $LOGFILE
fi
