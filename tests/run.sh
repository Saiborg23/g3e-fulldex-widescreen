#!/bin/bash
# run.sh NAME ROM WxH ASPECT "moves"  -  one scripted, headless session of Fulldex's GBA player.
#   GBAW_PLAYER   the test build of pokemon-gba-wide (see README.md: Fulldex's gba/ at the commit in
#                 fulldex-gba-player-test-harness.patch, mGBA with mgba-wide.patch + mgba-wide-test-switches.patch)
#   GBAW_TESTDIR  where runs are written (default: ./runs)
HERE="$(cd "$(dirname "$0")" && pwd)"
P="${GBAW_PLAYER:?set GBAW_PLAYER to the pokemon-gba-wide test build}"
T="${GBAW_TESTDIR:-$PWD/runs}"; mkdir -p "$T"
d=$T/$1-$RANDOM; mkdir -p $d/data; echo "widescreen=$4" > $d/data/settings.ini
python3 -I "$HERE/walk.py" $d/s.txt "$5"; sed -i '' "s#SHOTDIR#$d#" $d/s.txt
cd $d && SDL_VIDEODRIVER=dummy SDL_RENDER_DRIVER=software SDL_AUDIODRIVER=dummy "$P" --rom "$2" --data $d/data --window $3 --script $d/s.txt > $d/log.txt 2>&1
echo "$1 exit $? $(grep -m1 extra $d/log.txt | awk '{print $4,$5,$6}') -> $d"
