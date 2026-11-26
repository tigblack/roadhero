# Scarbound Car Combat: Idle RPG — loading screen refresh

Published public version 3 on 2026-11-13:
https://roadgame-wasteland-webgl.valeriy-haqv-7337.chatgpt.site

The selected name is **Scarbound Car Combat: Idle RPG**, exactly 30 characters including spaces and colon. The loading artwork carries a centered SCARBOUND / CAR COMBAT / IDLE RPG title. Unity product name, website title, visible branding and accessibility labels are updated. The technical RoadGame source paths, namespace and existing public URL remain stable. No Google Play listing was edited.

## Artwork

One original tall poster replaces the rejected four-image grid. Its nine irregular story panels show the hero car, Mammoth truck, raider team, desert convoy, repair garage, harpoon and scrap, goggled raider portrait, night checkpoint ambush and toxic marsh. The wide illustrated website background remains around the game on desktop.

- Generation: built-in image_gen; actual game screenshots and approved first-pass car/truck illustrations used as references.
- Final source: `Assets/RoadGame/Resources/Loading/loading-poster.png`, 941×1672.
- Web export: `Assets/WebGLTemplates/RoadGame/TemplateData/loading-poster.webp`, 593,844 bytes, WebP q86/method6.
- Exact generation prompt: `Tools/Art/loading-poster-prompt.txt`.
- References and export specification: `Tools/Art/loading-art-prompts.json`.
- Earlier artwork is archived outside Resources in `Docs/art-source/loading-first-pass`; it is not shipped as four runtime panels.

The complete image is contained without cropping. Native import preserves its non-power-of-two dimensions, with no mipmaps or CPU-readable copy. The title is a responsive HTML/native UI overlay, so the original poster remains reusable without lettering.

## Loading behavior

Unity's download callback supplies file progress. Game construction supplies separate monotone stage progress. A completed download or a displayed 100% does not dismiss the cover. Game readiness follows the first completed gameplay frame, then the WebGL bridge schedules the browser presentation frame. There is no minimum loading timer or artificial fade. Artwork decoding does not delay an already ready game. Errors keep the cover visible with a retry action.

## Verification

- Final Unity WebGL build succeeded: 0 errors. Unity package and toolchain warnings remain in `Logs/Build-WebGL.log`.
- Generated JavaScript syntax, all HTML/CSS asset references and gzip WebAssembly magic passed.
- Deterministic tests against the exact template and WebGL bridge covered slow progress, 90%/100% without readiness, readiness before the Unity initialization promise resolves, late callbacks and both loader/initialization error retries.
- Real Chrome desktop launch and the published public Site both reached gameplay. A separate origin with cache disabled and Build responses limited to 32 KiB every 75 ms kept the illustrated cover visible at 16% progress and subsequently entered gameplay.
- Mobile browser layout was rendered in an actual 390×844 iframe viewport; all nine panels, centered title, status and Start button fit. This is viewport testing, not a physical-phone test.
- Actual native Unity Canvas UI was rendered at 390×844 and 1920×1080, with explicit Canvas viewport assertions and 90% preview state. Reproduce with `RoadGame.EditorTools.LoadingPreview.Run` in a graphics-enabled Unity batch session.
- Anonymous HTTPS retrieval confirmed the published Scarbound HTML, final build references and byte-identical poster SHA256.

Screenshots are in `Docs/screenshots/loading-refresh/`: `desktop-loading.png`, `mobile-browser.png`, `browser-slow-loading.png`, `browser-slow-ready.png`, `native-portrait.png`, `native-desktop.png`, `public-loading.png`, `public-start.png`, and `public-ready.png`.

Sites source commit: `4912ad29bd030f6022d8716831c39b3c8c683714`.
Saved version: `appgprj_6af5f0d31bc08191a4303d673bef9a76~appgver_77716de04d048191befa124ae4bca5aa`.
Successful public deployment: `appgdep_6af623de24888191a0520af491a2d79a`.

Earlier name research remains in `Docs/google-play-name-proposals.md`, with the selected name recorded above those proposals.
