# Run once in every Cloud Shell tab you use:   source env.sh
# Loads .env into your shell (so $GOOGLE_CLOUD_PROJECT and $REGION work in the
# commands you type) and activates the Python environment (so `adk` is on PATH).
if [ ! -f .env ] || [ ! -d .venv ]; then
  echo "Run 'make setup' first (from the repo folder)."; return 1 2>/dev/null || exit 1
fi
set -a; . ./.env; set +a
. .venv/bin/activate
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
echo "ShopDesk env loaded: project=$GOOGLE_CLOUD_PROJECT region=${REGION:-us-central1}"
