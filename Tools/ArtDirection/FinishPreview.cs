using System.Reflection;
using UnityEngine;
using UnityEditor;

var helper = typeof(RoadGame.EditorTools.ArtDirectionCapture);
helper.GetMethod("SetGameViewSize", BindingFlags.NonPublic | BindingFlags.Static).Invoke(null, null);
await Awaitable.NextFrameAsync();
await Awaitable.NextFrameAsync();
var verified = RoadGame.EditorTools.ArtDirectionCapture.Verify();
var finished = RoadGame.EditorTools.ArtDirectionCapture.Finish();
return verified + "\n" + finished;
