# Game-dev навыки RoadGame

Установлены все **79 специализированных навыков и роутер** из [awesome-gamedev-agent-skills](https://github.com/gamedev-skills/awesome-gamedev-agent-skills).

- Область установки: только этот проект, `.agents/skills/`.
- Зафиксированный upstream commit: `c6ca6c41c839b68319ffc08430b99ab768debc32`.
- Дата установки: 2026-11-24.
- Полные папки навыков сохранены без правок: 80 `SKILL.md`, 162 дополнительных файла, включая справочники, шаблоны и скрипты.
- Лицензия: [Apache-2.0](LICENSE), уведомления авторов: [NOTICE](NOTICE).
- Источник, пути и SHA-256 каждого импортированного файла: [SOURCE.json](SOURCE.json).

## Как использовать

Codex обнаруживает проектные навыки в `.agents/skills/` и выбирает их по описанию; см. [официальную документацию](https://learn.chatgpt.com/docs/build-skills). Навыки доступны со следующего запроса. Если список не обновился, перезапустить Codex. Можно явно упомянуть `$router`, `$unity-physics` или другой навык.

На игровых задачах начинать с [router](../skills/router/SKILL.md), если подходящие навыки ещё не выбраны. Полные тексты всех 80 навыков одновременно не загружать. Основной проект — Unity; его версию читать из `ProjectSettings/ProjectVersion.txt`. На момент установки это **6000.6.4f1**; примеры библиотеки ориентированы на Unity 6.3 LTS и требуют проверки API для нашей версии. Наличие веб-оболочки в `Sites/` не делает игровой движок three.js или Phaser.

Навыки перенесены в плоскую структуру, как рекомендует upstream: исходный путь `skills/<category>/<name>/SKILL.md` здесь означает `.agents/skills/<name>/SKILL.md`. Внутренние `references/`, `scripts/`, `assets/` находятся рядом с соответствующим `SKILL.md`. Скрипты вызывать по полному пути к установленному навыку; относительный `scripts/...` из примера не означает корневую папку проекта.

Правила [AGENTS.md](../../AGENTS.md), запрос пользователя и текущая архитектура проекта определяют применение примеров. Все рабочие запуски остаются беззвучными: Unity batch с `-disableaudio`, браузер с `?mute`. Само наличие навыка не означает разрешение переписывать все ассеты, менять движок или публиковать игру. Вспомогательные скрипты при установке не запускались; движки, плагины и внешние сервисы библиотекой не устанавливались.

Примеры выбора:

| Задача | Навыки |
| --- | --- |
| Джойстик, управление машиной | `unity-input-system`, `input-systems`, `unity-physics` |
| Подвеска, столкновения, задний ход | `unity-physics`, `physics-tuning` |
| Рельеф и интересные маршруты | `level-design` + нужный Unity-навык |
| Враги и навигация | `game-ai`, `unity-navmesh` при использовании NavMesh |
| Память и производительность WebGL | `performance-optimization`, `unity-build-pipeline`, `unity-build-size` |
| Интерфейс телефона | `game-ui-ux`, `input-systems` |

## Документация библиотеки

- [Исходный README](UPSTREAM_README.md).
- [Поддержка версий движков](docs/VERSION-SUPPORT.md).
- [Установка](docs/INSTALLATION.md), [совместимость агентов](docs/COMPATIBILITY.md), [формат навыка](docs/SKILL-FORMAT.md).

Автоматическое обновление не включено. При обновлении проверять новую ревизию и сохранять проектные правила; SHA-256 в `SOURCE.json` относится к установленной ревизии.

## Полный каталог

| Категория | Навык |
| --- | --- |
| router | [router](../skills/router/SKILL.md) |
| disciplines | [ai-behavior-trees-utility-ai](../skills/ai-behavior-trees-utility-ai/SKILL.md) |
| disciplines | [audio-design](../skills/audio-design/SKILL.md) |
| disciplines | [camera-systems](../skills/camera-systems/SKILL.md) |
| disciplines | [create-game-assets](../skills/create-game-assets/SKILL.md) |
| disciplines | [dialogue-systems](../skills/dialogue-systems/SKILL.md) |
| disciplines | [game-ai](../skills/game-ai/SKILL.md) |
| disciplines | [game-feel](../skills/game-feel/SKILL.md) |
| disciplines | [game-ui-ux](../skills/game-ui-ux/SKILL.md) |
| disciplines | [input-systems](../skills/input-systems/SKILL.md) |
| disciplines | [level-design](../skills/level-design/SKILL.md) |
| disciplines | [performance-optimization](../skills/performance-optimization/SKILL.md) |
| disciplines | [physics-tuning](../skills/physics-tuning/SKILL.md) |
| disciplines | [procedural-gen](../skills/procedural-gen/SKILL.md) |
| disciplines | [save-systems](../skills/save-systems/SKILL.md) |
| disciplines | [shader-programming](../skills/shader-programming/SKILL.md) |
| ebitengine | [ebitengine-game](../skills/ebitengine-game/SKILL.md) |
| genres | [card-game](../skills/card-game/SKILL.md) |
| genres | [fps-shooter](../skills/fps-shooter/SKILL.md) |
| genres | [platformer](../skills/platformer/SKILL.md) |
| genres | [puzzle](../skills/puzzle/SKILL.md) |
| genres | [roguelike](../skills/roguelike/SKILL.md) |
| genres | [rpg](../skills/rpg/SKILL.md) |
| genres | [survival-crafting](../skills/survival-crafting/SKILL.md) |
| genres | [tower-defense](../skills/tower-defense/SKILL.md) |
| genres | [visual-novel](../skills/visual-novel/SKILL.md) |
| godot | [godot-2d-movement](../skills/godot-2d-movement/SKILL.md) |
| godot | [godot-3d-essentials](../skills/godot-3d-essentials/SKILL.md) |
| godot | [godot-animation](../skills/godot-animation/SKILL.md) |
| godot | [godot-audio](../skills/godot-audio/SKILL.md) |
| godot | [godot-csharp](../skills/godot-csharp/SKILL.md) |
| godot | [godot-export](../skills/godot-export/SKILL.md) |
| godot | [godot-gdscript](../skills/godot-gdscript/SKILL.md) |
| godot | [godot-gdscript-headless-testing](../skills/godot-gdscript-headless-testing/SKILL.md) |
| godot | [godot-multiplayer](../skills/godot-multiplayer/SKILL.md) |
| godot | [godot-nodes-scenes](../skills/godot-nodes-scenes/SKILL.md) |
| godot | [godot-physics](../skills/godot-physics/SKILL.md) |
| godot | [godot-resources](../skills/godot-resources/SKILL.md) |
| godot | [godot-shaders](../skills/godot-shaders/SKILL.md) |
| godot | [godot-signals-groups](../skills/godot-signals-groups/SKILL.md) |
| godot | [godot-tilemap](../skills/godot-tilemap/SKILL.md) |
| godot | [godot-ui-control](../skills/godot-ui-control/SKILL.md) |
| other-engines | [bevy-ecs](../skills/bevy-ecs/SKILL.md) |
| other-engines | [defold-core](../skills/defold-core/SKILL.md) |
| other-engines | [love2d-core](../skills/love2d-core/SKILL.md) |
| other-engines | [pygame-core](../skills/pygame-core/SKILL.md) |
| other-engines | [roblox-characters](../skills/roblox-characters/SKILL.md) |
| other-engines | [roblox-datastores](../skills/roblox-datastores/SKILL.md) |
| other-engines | [roblox-luau](../skills/roblox-luau/SKILL.md) |
| other-engines | [roblox-networking](../skills/roblox-networking/SKILL.md) |
| other-engines | [roblox-physics](../skills/roblox-physics/SKILL.md) |
| other-engines | [roblox-simulator-economy](../skills/roblox-simulator-economy/SKILL.md) |
| other-engines | [roblox-studio-workflow](../skills/roblox-studio-workflow/SKILL.md) |
| other-engines | [roblox-ui](../skills/roblox-ui/SKILL.md) |
| unity | [unity-animation](../skills/unity-animation/SKILL.md) |
| unity | [unity-build-pipeline](../skills/unity-build-pipeline/SKILL.md) |
| unity | [unity-build-size](../skills/unity-build-size/SKILL.md) |
| unity | [unity-csharp-scripting](../skills/unity-csharp-scripting/SKILL.md) |
| unity | [unity-input-system](../skills/unity-input-system/SKILL.md) |
| unity | [unity-navmesh](../skills/unity-navmesh/SKILL.md) |
| unity | [unity-physics](../skills/unity-physics/SKILL.md) |
| unity | [unity-scriptableobjects](../skills/unity-scriptableobjects/SKILL.md) |
| unity | [unity-tilemap-2d](../skills/unity-tilemap-2d/SKILL.md) |
| unreal | [unreal-behavior-trees](../skills/unreal-behavior-trees/SKILL.md) |
| unreal | [unreal-blueprints](../skills/unreal-blueprints/SKILL.md) |
| unreal | [unreal-cpp-gameplay](../skills/unreal-cpp-gameplay/SKILL.md) |
| unreal | [unreal-enhanced-input](../skills/unreal-enhanced-input/SKILL.md) |
| unreal | [unreal-niagara](../skills/unreal-niagara/SKILL.md) |
| unreal | [unreal-packaging](../skills/unreal-packaging/SKILL.md) |
| web-engines | [phaser-arcade-physics](../skills/phaser-arcade-physics/SKILL.md) |
| web-engines | [phaser-core](../skills/phaser-core/SKILL.md) |
| web-engines | [pixijs-rendering](../skills/pixijs-rendering/SKILL.md) |
| web-engines | [threejs-gltf-loading](../skills/threejs-gltf-loading/SKILL.md) |
| web-engines | [threejs-materials-lighting](../skills/threejs-materials-lighting/SKILL.md) |
| web-engines | [threejs-scene-setup](../skills/threejs-scene-setup/SKILL.md) |
| workflows | [game-docs](../skills/game-docs/SKILL.md) |
| workflows | [game-jam](../skills/game-jam/SKILL.md) |
| workflows | [itch-publish](../skills/itch-publish/SKILL.md) |
| workflows | [prototype-fast](../skills/prototype-fast/SKILL.md) |
| workflows | [steam-publish](../skills/steam-publish/SKILL.md) |
