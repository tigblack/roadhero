#!/bin/zsh
# Scarbound music: compose -> render (music-production skill) -> 44.1 kHz / 16-bit loop for Unity -> measurements.
#
#   Tools/MusicGen/make_music.sh [theme|sketches|all] [--install]
#
# Writes into ArtSource/Audio/Music (sketches/, theme/). Only with --install does it replace the game's
# Assets/RoadGame/Resources/Audio/music_theme.wav (its .meta and GUID are never touched).
# Nothing here plays audio. Setup and sources: Tools/MusicGen/README.md.
set -e
WHAT=${1:-all}
INSTALL=0
[[ "$2" == "--install" || "$1" == "--install" ]] && INSTALL=1
[[ "$WHAT" == "--install" ]] && WHAT=all

ROOT=${0:A:h:h:h}                                   # the Unity project
MG=$ROOT/Tools/MusicGen
SKILL=${MUSIC_SKILL:-$HOME/.music-skill/music-skill/skills/music-production}
CONFIG=${MUSIC_SKILL_CONFIG:-$HOME/.music-skill/local-config.studio.json}
PY=${MUSIC_PY:-$HOME/.music-skill/.venv/bin/python}
[[ -f "$SKILL/scripts/studio.py" && -f "$CONFIG" && -x "$PY" ]] || { echo "music-production skill not set up: see $MG/README.md"; exit 2; }
# python.org builds of Python on macOS ship without root certificates; the skill only needs them for downloads
export SSL_CERT_FILE=${SSL_CERT_FILE:-$($PY -c 'import certifi; print(certifi.where())' 2>/dev/null)}

STAMP=$(date +%Y%m%d-%H%M%S)
WORK=${MUSIC_WORK:-${TMPDIR:-/tmp}/scarbound-music}
OUT=$ROOT/ArtSource/Audio/Music
mkdir -p "$WORK" "$OUT/sketches" "$OUT/theme"

render() {   # piece -> $WORK/<piece>/render-<stamp>
  local piece=$1
  $PY "$MG/scarbound_music.py" $piece "$WORK/$piece"
  $PY "$SKILL/scripts/studio.py" review "$WORK/$piece/song.json" --output "$WORK/$piece/review-$STAMP" --config "$CONFIG" | head -3
  $PY "$SKILL/scripts/studio.py" render "$WORK/$piece/song.json" --config "$CONFIG" --output "$WORK/$piece/render-$STAMP" \
    | grep -E "^Render|^Master|Failed|ERROR|^Loop"
}

if [[ "$WHAT" == sketches || "$WHAT" == all ]]; then
  for pair in sketch1:01_road_blues_groove sketch2:02_open_horizon sketch3:03_scrap_machine; do
    p=${pair%%:*}; n=${pair##*:}
    render $p
    R=$WORK/$p/render-$STAMP
    $PY "$MG/finalize.py" "$R/loop.wav" "$OUT/sketches/$n.wav" --bars 12 --mp3 "$OUT/sketches/$n.mp3" --master "$R/master.wav"
    cp "$WORK/$p/song.json" "$OUT/sketches/${n}_song.json"; cp "$R/composition.mid" "$OUT/sketches/$n.mid"
  done
  $PY "$MG/measure.py" "$OUT"/sketches/*.wav --loop
fi

if [[ "$WHAT" == theme || "$WHAT" == all ]]; then
  render theme
  R=$WORK/theme/render-$STAMP
  N=scarbound_dust_road_groove
  D=$OUT/theme
  mkdir -p "$D/stems" "$D/midi" "$D/reports"
  $PY "$MG/finalize.py" "$R/loop.wav" "$WORK/theme/music_theme.wav" --bars 48 --hi24 "$D/${N}_loop_44k_24bit.wav" \
      --mp3 "$D/${N}_preview.mp3" --master "$R/master.wav"
  cp "$R/loop.wav" "$D/${N}_loop_48k_24bit.wav"
  cp "$R/master.flac" "$D/${N}_master_48k_24bit_with_tail.flac"
  cp "$WORK/theme/song.json" "$D/${N}_song.json"
  cp "$R/composition.mid" "$D/midi/${N}_performed.mid"; cp "$R/score.mid" "$D/midi/${N}_score.mid"; cp "$R"/midi/*.mid "$D/midi/"
  cp "$R/loop.json" "$R/report.json" "$R/stem_receipts.json" "$D/reports/"
  for s in "$R"/stems/*.wav; do
    ffmpeg -hide_banner -loglevel error -y -i "$s" -c:a flac -sample_fmt s32 -compression_level 8 "$D/stems/${s:t:r}.flac"
  done
  $PY "$SKILL/scripts/studio.py" analyze "$R" --output "$R/analysis.json" --config "$CONFIG" | head -1
  cp "$R/analysis.json" "$D/reports/analysis.json"
  $PY "$MG/measure.py" "$WORK/theme/music_theme.wav" --loop --json "$D/reports/measure_music_theme_unity.json"
  if (( INSTALL )); then
    A=$ROOT/Assets/RoadGame/Resources/Audio
    meta_before=$(shasum -a 256 "$A/music_theme.wav.meta" | cut -d' ' -f1)
    cp "$WORK/theme/music_theme.wav" "$A/music_theme.wav"
    [[ $(shasum -a 256 "$A/music_theme.wav.meta" | cut -d' ' -f1) == $meta_before ]] || { echo "meta changed?!"; exit 3; }
    echo "installed -> $A/music_theme.wav (meta untouched)"
  else
    echo "game file not replaced (add --install): $WORK/theme/music_theme.wav"
  fi
fi
