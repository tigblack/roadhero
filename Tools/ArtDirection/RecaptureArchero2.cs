using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using UnityEditor;
using UnityEngine;
using Newtonsoft.Json.Linq;

// Re-render an already styled frozen preview, rejecting URP's cyan loading fallback.
var flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;
var helper = typeof(RoadGame.EditorTools.ArtDirectionCapture);
bool oldAsync = ShaderUtil.allowAsyncCompilation;
try {
    ShaderUtil.allowAsyncCompilation = false;
    var mats = (Dictionary<Material, Material>)helper.GetField("previewMaterials", flags).GetValue(null);
    foreach (var m in mats.Values) {
        for (int p = 0; p < m.passCount; p++) ShaderUtil.CompilePass(m,p,true);
    }
    helper.GetMethod("SetGameViewSize",flags).Invoke(null,null);
    for (int i = 0; i < 8; i++) await Awaitable.NextFrameAsync();
    string before = RoadGame.EditorTools.ArtDirectionCapture.Verify();
    if (ShaderUtil.ShaderHasError(Shader.Find("Hidden/RoadGame/ArcheroDirection"))) throw new Exception("Shader compile failed.");
    var cmds = AppDomain.CurrentDomain.GetAssemblies().Select(a=>a.GetType("Unity.Pipeline.Editor.Commands.Capture.CaptureCommands")).First(t=>t!=null);
    var result = cmds.GetMethod("CaptureGameView",flags).Invoke(null,new object[] { 540,1170,null,Path.GetFullPath("ArtDirectionScreenshots/06_archero_2.png"),false,0,"screen",null });
    var msg = result.GetType().GetProperty("Message",flags)?.GetValue(result)?.ToString();
    if (!string.IsNullOrWhiteSpace(msg)) throw new Exception("Rejected capture: " + msg);
    string after = RoadGame.EditorTools.ArtDirectionCapture.Verify();
    if (before != after) throw new Exception("Frozen state changed during recapture.");
    var reportPath = Path.GetFullPath("ArtDirectionScreenshots/06_archero2-verification.json");
    var report = JObject.Parse(File.ReadAllText(reportPath));
    report["before"] = before; report["after"] = after;
    report["synchronousShaderCompilation"] = true;
    File.WriteAllText(reportPath,report.ToString());
    return after + "; synchronously compiled actual shader variants.";
} finally { ShaderUtil.allowAsyncCompilation = oldAsync; }
