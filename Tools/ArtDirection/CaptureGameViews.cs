using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using Newtonsoft.Json;
using UnityEngine;
using UnityEditor;

// Run with: unity command --timeout 90 script eval --file Tools/ArtDirection/CaptureGameViews.cs --timeout 90
// All five are read from the same pinned GameView inside one Unity command. Batch-mode Unity
// may destroy non-docked EditorWindows between client transactions; no fallback size is accepted.
var flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static | BindingFlags.Instance;
var helper = typeof(RoadGame.EditorTools.ArtDirectionCapture);
var captureCommands = AppDomain.CurrentDomain.GetAssemblies()
    .Select(a => a.GetType("Unity.Pipeline.Editor.Commands.Capture.CaptureCommands"))
    .First(t => t != null);
var captureMethod = captureCommands.GetMethod("CaptureGameView", flags);
string[] files = { "01_casual_3d.png", "02_realistic.png", "03_low_poly.png", "04_comic_cel_shading.png", "05_pixel_art.png" };
var records = new List<Dictionary<string, string>>();
for (int style = 0; style < 5; style++)
{
    helper.GetMethod("SetGameViewSize", flags).Invoke(null, null);
    await Awaitable.NextFrameAsync();
    await Awaitable.NextFrameAsync();
    RoadGame.EditorTools.ArtDirectionCapture.Apply(style);
    if(style==3) { var ink=(Material)helper.GetField("inkMaterial",flags).GetValue(null); ink.SetFloat("_OutlineWidth",3.5f); ink.renderQueue=2001; }
    // Let URP render the new materials to the GameView; all gameplay, FX and HUD are frozen.
    await Awaitable.NextFrameAsync();
    await Awaitable.NextFrameAsync();
    string before = RoadGame.EditorTools.ArtDirectionCapture.Verify();
    var result = captureMethod.Invoke(null, new object[] {
        540, 1170, null, Path.GetFullPath("ArtDirectionScreenshots/" + files[style]), false, 0, "screen", null
    });
    var message = result.GetType().GetProperty("Message", flags)?.GetValue(result)?.ToString();
    if (!string.IsNullOrWhiteSpace(message)) throw new Exception("Rejected capture: " + message);
    string after = RoadGame.EditorTools.ArtDirectionCapture.Verify();
    if (before != after) throw new Exception("Scene changed while capturing " + files[style]);
    records.Add(new Dictionary<string, string> {
        { "file", files[style] }, { "before", before }, { "after", after }, { "source", "Unity GameView m_TargetTexture, via installed Pipeline CaptureGameView(source=screen)" }
    });
    Debug.Log("ArtDirection FINAL: " + files[style] + " " + after);
}
File.WriteAllText(Path.GetFullPath("ArtDirectionScreenshots/verification.json"), JsonConvert.SerializeObject(records, Formatting.Indented));
return "Captured five fixed GameView PNGs at540x1170; exact transforms/projection/HP/HUD and actual GameView render target verified before and after every capture.";
