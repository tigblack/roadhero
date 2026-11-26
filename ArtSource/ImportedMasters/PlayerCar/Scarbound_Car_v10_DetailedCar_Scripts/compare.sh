#!/bin/zsh
# Side-by-side before/after sheets with label strips (ffmpeg hstack/vstack; labels rendered by Blender).
R="/Users/arthuri/Blender Proj/car/Scarbound_Car_v10_DetailedCar_Renders"
L="$R/_labels"
mkdir -p "$R/compare"
for f in "$R"/before/before_*.png; do
  base=${f:t:r}; view=${base#before_}
  a="$R/after/after_${view}.png"
  [[ -f "$a" ]] || continue
  w=$(sips -g pixelWidth "$f" | awk '/pixelWidth/{print $2}')
  lh=$(( w * 96 / 1600 ))
  ffmpeg -loglevel error -y -i "$f" -i "$a" -i "$L/label_before.png" -i "$L/label_after.png" -filter_complex \
    "[2]scale=${w}:${lh}[lb];[3]scale=${w}:${lh}[la];[lb][0]vstack[x];[la][1]vstack[y];[x][y]hstack=inputs=2,pad=iw+0:ih:0:0" \
    -frames:v 1 "$R/compare/compare_${view}.png"
  echo "compare_${view}.png"
done
