#!/usr/bin/env bash
set -euo pipefail

transition_block="${1:?Pass a future transition block number.}"
block_period="${2:-10}"
empty_block_period="${3:-60}"
genesis=/generated/genesis.json
temporary=/generated/genesis.timing.json

if ! sed -n '/"qbft"[[:space:]]*:[[:space:]]*{/,/"requesttimeoutseconds"/p' "$genesis" | head -n 8 | grep -q '"xemptyblockperiodseconds"'; then
  sed -i "/\"blockperiodseconds\"[[:space:]]*:[[:space:]]*[0-9][0-9]*,/a\\      \"xemptyblockperiodseconds\" : ${empty_block_period}," "$genesis"
  echo "Configured the Besu 25.x base empty-block period at ${empty_block_period}s."
fi

if grep -q '"transitions"' "$genesis"; then
  echo "The generated genesis already contains a timing transition; leaving that transition unchanged."
  exit 0
fi

awk -v transition_block="$transition_block" -v block_period="$block_period" -v empty_block_period="$empty_block_period" '
  !inserted && /"requesttimeoutseconds"[[:space:]]*:/ {
    print
    if ((getline next_line) <= 0) exit 2
    sub(/}[[:space:]]*$/, "},", next_line)
    print next_line
    print "    \"transitions\" : {"
    print "      \"qbft\" : [ {"
    print "        \"block\" : " transition_block ","
    print "        \"blockperiodseconds\" : " block_period ","
    print "        \"xemptyblockperiodseconds\" : " empty_block_period
    print "      } ]"
    print "    }"
    inserted=1
    next
  }
  { print }
  END { if (!inserted) exit 3 }
' "$genesis" > "$temporary"

mv "$temporary" "$genesis"
echo "QBFT timing transition scheduled at block ${transition_block}: transaction blocks >= ${block_period}s, empty blocks >= ${empty_block_period}s."
