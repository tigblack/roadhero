QA="/Users/arthuri/Blender Proj/New Folder(1)/.claude/skills/blender-asset-qa/scripts/qa_check.py"
F="/Users/arthuri/Blender Proj/car/Scarbound_Car_v10_DetailedCar.blend"
for grp in "GunMesh GunCradle Turntable HoodMount" "Wheel.082 Wheel.083 Wheel.085 Wheel.087 BrakeCaliper_FL BrakeCaliper_FR BrakeCaliper_RL BrakeCaliper_RR" "TurretBase.001 Column LauncherMesh HarpoonTip" "Cloak HeadMesh UpperArmR UpperArmL ForeArmR ForeArmL HandR HandL LegMesh LegMesh.001" "Body.573 Details Underbody"; do
/Applications/Blender.app/Contents/MacOS/Blender -b "$F" --factory-startup -noaudio --python "$QA" -- --objects $grp --profile game 2>/dev/null | grep "@@JSON@@" | sed 's/@@JSON@@//' > /tmp/claude_qa_tmp.json
python3 - "$grp" <<'PY'
import json, sys, re, collections
d = json.load(open('/tmp/claude_qa_tmp.json'))
grp = sys.argv[1]
errs = d.get('errors', [])
kinds = collections.Counter(re.sub(r'\(.*|\[.*', '', e).strip()[:70] for e in errs)
print('GROUP', grp[:50], '| pass', d.get('pass'), '| errors', len(errs), '| warnings', len(d.get('warnings', [])))
for k, n in kinds.most_common(8): print('   E', n, 'x', k)
for w in d.get('warnings', [])[:4]: print('   W', w[:120])
PY
done
