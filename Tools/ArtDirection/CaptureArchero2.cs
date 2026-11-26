using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using UnityEngine.UI;
using UnityEditor;
using RoadGame;

// Evaluate through the connected Unity Editor after Begin() has reached "frozen".
// The first five PNGs and their reports are deliberately never written here.
bool oldAsyncCompilation = ShaderUtil.allowAsyncCompilation;
ShaderUtil.allowAsyncCompilation = false;
try {
var flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;
var helper = typeof(RoadGame.EditorTools.ArtDirectionCapture);
var captureCommands = AppDomain.CurrentDomain.GetAssemblies()
    .Select(a => a.GetType("Unity.Pipeline.Editor.Commands.Capture.CaptureCommands")).First(t => t != null);
var captureMethod = captureCommands.GetMethod("CaptureGameView", flags);
var temporary = (List<UnityEngine.Object>)helper.GetField("temporary", flags).GetValue(null);
var originals = (Dictionary<MeshFilter, Mesh>)helper.GetField("originalMeshes", flags).GetValue(null);
var materials = (Dictionary<Material, Material>)helper.GetField("previewMaterials", flags).GetValue(null);
var enemy = (Enemy)helper.GetField("enemy", flags).GetValue(null);
var g = Game.I;
float[] V3(Vector3 v) => new[] { v.x, v.y, v.z };
float[] V2(Vector2 v) => new[] { v.x, v.y };
float[] Q(Quaternion v) => new[] { v.x, v.y, v.z, v.w };
float[] C(Color v) => new[] { v.r, v.g, v.b, v.a };
float[] M(Matrix4x4 v) => Enumerable.Range(0, 16).Select(i => v[i]).ToArray();
string Hierarchy(Transform t) => (t.parent == null ? "" : Hierarchy(t.parent) + "/") + t.name + "[" + t.GetSiblingIndex() + "]";
object Snapshot() => new {
    scene = "Assets/Scenes/Game.unity", resolution = new[] { 540,1170 },
    camera = new { position = V3(g.cam.transform.position), euler = V3(g.cam.transform.eulerAngles),
        rotation = Q(g.cam.transform.rotation), fov = g.cam.fieldOfView, aspect = g.cam.aspect,
        projection = M(g.cam.projectionMatrix), nonJitteredProjection = M(g.cam.nonJitteredProjectionMatrix) },
    player = new { position = V3(g.player.Pos), rotation = Q(g.player.transform.rotation), hp = g.progress.d.hp },
    enemy = new { position = V3(enemy.Pos), rotation = Q(enemy.transform.rotation), hp = enemy.hp },
    gems = g.progress.d.gems, weaponLevel = g.progress.d.weaponLevel[0], weaponCopies = g.progress.d.weaponCopies[0],
    hud = UnityEngine.Object.FindObjectsByType<Text>(FindObjectsSortMode.None).OrderBy(t => Hierarchy(t.transform)).Select(t => new {
        path = Hierarchy(t.transform), text = t.text, color = C(t.color), active = t.gameObject.activeInHierarchy,
        position = V3(t.rectTransform.localPosition), rotation = Q(t.rectTransform.localRotation), scale = V3(t.rectTransform.localScale),
        size = V2(t.rectTransform.sizeDelta), anchorMin = V2(t.rectTransform.anchorMin), anchorMax = V2(t.rectTransform.anchorMax),
        pivot = V2(t.rectTransform.pivot), anchored = V2(t.rectTransform.anchoredPosition)
    }).ToArray()
};
string Capture(string output) {
    var result = captureMethod.Invoke(null, new object[] { 540,1170,null,Path.GetFullPath(output),false,0,"screen",null });
    var message = result.GetType().GetProperty("Message",flags)?.GetValue(result)?.ToString();
    if (!string.IsNullOrWhiteSpace(message)) throw new Exception("Rejected capture: " + message);
    return output;
}
helper.GetMethod("SetGameViewSize",flags).Invoke(null,null);
await Awaitable.NextFrameAsync();
await Awaitable.NextFrameAsync();
RoadGame.EditorTools.ArtDirectionCapture.Apply(0);
await Awaitable.NextFrameAsync();
await Awaitable.NextFrameAsync();
string before = RoadGame.EditorTools.ArtDirectionCapture.Verify();
string snapshotBefore = JsonConvert.SerializeObject(Snapshot(), Formatting.Indented);
Capture("/tmp/scarbound-sixth-control-casual.png");

var shader = AssetDatabase.LoadAssetAtPath<Shader>("Assets/RoadGame/Editor/ArtDirection/ArcheroDirection.shader");
if (shader == null || ShaderUtil.ShaderHasError(shader)) throw new Exception("Archero preview shader did not compile.");
bool linear = QualitySettings.activeColorSpace == ColorSpace.Linear;
Color Paint(string hex) { ColorUtility.TryParseHtmlString(hex, out var c); return linear ? c.linear : c; }
foreach (var pair in materials) {
    var m = pair.Value;
    m.shader = shader;
    m.CopyMatchingPropertiesFromMaterial(pair.Key);
    m.SetFloat("_Ground",pair.Key.name == "Ground" ? 1f : pair.Key.name.StartsWith("Road") ? 2f : 0f);
    m.SetColor("_FloorTint", Paint("#EED6BA"));
    m.SetColor("_RoadTint", Paint("#9991A8"));
    m.SetColor("_LaneTint", Paint("#F6E4A0"));
    m.SetColor("_UndersideTint", Paint("#B9ACDC"));
    m.SetColor("_HighlightTint", Paint("#FFF3D8"));
    m.SetFloat("_ContactStrength",.16f);
    m.SetFloat("_Brightness",1.05f);
    m.SetFloat("_GlossMul",.55f);
    m.SetFloat("_ShadowStrength",.8f);
}
var recolorReport = new List<object>();
foreach (var pair in originals) {
    string source = pair.Value.name;
    Dictionary<string,string> palette = null;
    if (source == "playercar_v2" || source == "playercar_v2_extras")
        palette = new Dictionary<string,string> { {"#131518","#62C9B1"}, {"#1B2830","#31576C"} };
    else if (source == "boss_mammoth")
        palette = new Dictionary<string,string> { {"#9A4E2A","#E57E79"}, {"#C26A3A","#F0A392"}, {"#7E3E20","#AB647D"} };
    if (palette == null) continue;
    var mesh = UnityEngine.Object.Instantiate(pair.Key.sharedMesh);
    mesh.name = "Archero2 preview / " + source;
    var colors = mesh.colors;
    int changed = 0;
    var swaps = palette.Select(p => new KeyValuePair<Color,Color>(Paint(p.Key),Paint(p.Value))).ToArray();
    for (int i = 0; i < colors.Length; i++) {
        foreach (var swap in swaps) {
            var d = new Vector3(colors[i].r-swap.Key.r,colors[i].g-swap.Key.g,colors[i].b-swap.Key.b);
            if (d.sqrMagnitude > 0.00000001f) continue;
            float a = colors[i].a;
            colors[i] = swap.Value;
            colors[i].a = a;
            changed++;
            break;
        }
    }
    mesh.colors = colors;
    pair.Key.sharedMesh = mesh;
    temporary.Add(mesh);
    recolorReport.Add(new { mesh = source, vertices = colors.Length, changed });
}
g.sun.color = new Color(1f,.98f,.94f);
g.sun.intensity = 1.05f;
g.sun.shadows = LightShadows.Soft;
g.sun.shadowStrength = .48f;
g.sun.transform.rotation = Quaternion.Euler(52f,135f,0);
RenderSettings.ambientSkyColor = new Color(.76f,.75f,.9f);
RenderSettings.ambientEquatorColor = new Color(.58f,.56f,.65f);
RenderSettings.ambientGroundColor = new Color(.39f,.35f,.43f);
var grade = (Volume)helper.GetField("grade",flags).GetValue(null);
grade.sharedProfile.components.Clear();
var colorGrade = grade.sharedProfile.Add<ColorAdjustments>(true);
colorGrade.saturation.Override(8f);
colorGrade.contrast.Override(0f);
colorGrade.postExposure.Override(0f);
grade.sharedProfile.Add<Tonemapping>(true).mode.Override(TonemappingMode.Neutral);
var bloom = grade.sharedProfile.Add<Bloom>(true);
bloom.threshold.Override(1.25f); bloom.intensity.Override(.12f);
EditorApplication.QueuePlayerLoopUpdate();
await Awaitable.NextFrameAsync();
await Awaitable.NextFrameAsync();
string after = RoadGame.EditorTools.ArtDirectionCapture.Verify();
string snapshotAfter = JsonConvert.SerializeObject(Snapshot(),Formatting.Indented);
if (snapshotBefore != snapshotAfter || before != after) throw new Exception("Camera/pose/HUD moved while applying the sixth look.");
Capture("ArtDirectionScreenshots/06_archero_2.png");
string final = RoadGame.EditorTools.ArtDirectionCapture.Verify();
if (after != final) throw new Exception("Scene moved during final capture.");
File.WriteAllText(Path.GetFullPath("ArtDirectionScreenshots/06_archero2-snapshot.json"),snapshotAfter);
File.WriteAllText(Path.GetFullPath("ArtDirectionScreenshots/06_archero2-verification.json"), JsonConvert.SerializeObject(new {
    file = "06_archero_2.png", style = "Archero 2 inspired, own RoadGame geometry/HUD",
    source = "actual Unity GameView m_TargetTexture via Pipeline CaptureGameView(source=screen)",
    before, after = final, sameCameraPoseHudBeforeAfter = snapshotBefore == snapshotAfter,
    roundedMeshes = true, recolors = recolorReport, reference = "https://play.google.com/store/apps/details?id=com.xq.archeroii&hl=en"
},Formatting.Indented));
return "Captured 06_archero_2.png at540x1170 from actual Unity GameView; fixed camera, player, Mammoth, HP and HUD verified. " + JsonConvert.SerializeObject(recolorReport);
} finally {
    ShaderUtil.allowAsyncCompilation = oldAsyncCompilation;
}
