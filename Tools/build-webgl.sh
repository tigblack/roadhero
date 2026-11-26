#!/usr/bin/env bash
set -euo pipefail

project_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
unity_editor="${UNITY_EDITOR_PATH:-/Applications/Unity/Hub/Editor/6000.6.4f1/Unity.app/Contents/MacOS/Unity}"
output_dir="${1:-$project_dir/Sites/roadgame-webgl/dist}"
mkdir -p "$project_dir/Logs"

"$unity_editor" -batchmode -disableaudio -quit \
  -projectPath "$project_dir" \
  -buildTarget WebGL \
  -executeMethod RoadGame.EditorTools.BuildTool.BuildWebGL \
  -buildOut "$output_dir" \
  -logFile "$project_dir/Logs/Build-WebGL.log"
