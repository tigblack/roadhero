# Sixth direction: Archero 2 inspired

`06_archero_2.png` is a 540×1170 PNG from the actual Unity GameView in `Assets/Scenes/Game.unity`. It adapts the clean painted volume and clear color separation in [Habby's official Archero 2 screenshots](https://play.google.com/store/apps/details?id=com.xq.archeroii&hl=en) to RoadGame's own vehicles, Dust Flats location and HUD. No Archero assets or generated paint-over images were used.

The player has mint paint, the Mammoth has coral paint, and the surroundings use pale sand and a muted violet road. Rounded copies of the existing meshes, a dedicated URP shader, broad cream highlights, soft violet form shading, gentle shadows and restrained bloom create the look. The HUD remains in its existing layout.

The original encounter was re-staged using the same preview setup. Camera position/rotation/FOV, player and Mammoth positions, HP and resolution match the original capture manifest. Currency245, weapon level4, player damage273 and the144! hit label were also checked. A same-run control render of the first style was compared visually with the original first PNG. The original five PNGs and their three reports remain byte-identical.

During this sixth capture, camera matrices, poses, HP and HUD were checked before and after the style change; the JSON snapshots were identical. The actual pinned GameView render target was540×1170. The current-run fingerprint is recorded in `06_archero2-verification.json`; Unity object IDs make that fingerprint session-specific, so it is not used to claim equality with the earlier session. `06_archero2-snapshot.json` records comparable values without object IDs. The previously captured screenshots do not have full JSON snapshots, so only their documented fields and visible composition can be compared retrospectively.

The final PNG was opened at full resolution and as a180×390 thumbnail. A second reviewer checked player/enemy/HUD readability and comparison with the previous framing. Shader variants were compiled synchronously before final capture to exclude Unity's cyan loading shader.

Reproduce in the connected Unity Editor: compile the editor helpers, set `ArtDirectionCapture.ManifestPath = "ArtDirectionScreenshots/06_archero2-manifest.txt"`, call `Begin()`, wait for state `frozen`, then evaluate `Tools/ArtDirection/CaptureArchero2.cs`. Finish using `Tools/ArtDirection/FinishPreview.cs`. Materials, meshes and render settings are temporary Play Mode copies, and the preview uses an isolated save suffix.
