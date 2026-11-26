# Tools/MusicGen — музыка Scarbound

Воспроизводимый процесс создания музыкальной темы:

1. Партитура пишется нота за нотой в Python.
2. Skill [music-production](https://github.com/owoevan-dev/music-skill) рендерит её на сэмплах CC0 и Surge XT, сводит и делает бесшовный луп.
3. Отсюда получается игровой WAV 44.1 кГц / 16 бит.

Описание самой музыки, проверки и лицензии — в `ArtSource/Audio/Music/README.md`.

Ничего здесь не воспроизводит звук. Рендер офлайн, плееры не запускаются.

`Tools/AudioGen/gen_audio.py` (эффекты) тему больше не пишет. Старую тему он запишет поверх новой только с флагом `--legacy-theme`.

## Файлы

| Файл | Что делает |
|---|---|
| `scarbound_music.py` | Вся музыка: мотив, рифф, гармония, грувы, три эскиза (`sketch1..3`) и тема (`theme`). Пишет `song.json` |
| `make_music.sh` | Партитура → review → рендер → `finalize.py` → `ArtSource/Audio/Music/…`. С `--install` заменяет `Assets/RoadGame/Resources/Audio/music_theme.wav` (`.meta` не трогает, проверяет хэш) |
| `finalize.py` | Луп 48 кГц / 24 бит → 44.1 кГц / 16 бит (см. ниже) |
| `measure.py` | Измерения: LUFS-I и LRA (BS.1770-4 / EBU 3342), true peak, моно, модель телефонного динамика, доли полос, стык лупа |

### finalize.py

- **Ресемплинг.** Луп пересчитывается как один период периодического сигнала (FFT по всему лупу): последний сэмпл переходит в первый так же, как в исходнике. При 100 BPM длина целая в обеих частотах: 5 529 600 → 5 080 320.
- **True peak** (4×) не выше −1 dBTP.
- **TPDF-дизеринг** с фиксированным зерном.

## Установка (один раз)

Всё живёт в `~/.music-skill`, вне проекта:

```zsh
brew install fluid-synth                      # ffmpeg уже есть (/opt/homebrew/bin/ffmpeg)
mkdir -p ~/.music-skill && cd ~/.music-skill
git clone https://github.com/owoevan-dev/music-skill.git && git -C music-skill checkout ba4338a958132ad6e5664fb6a767369dcb51c102
python3 -m venv .venv
.venv/bin/python -m pip install -r music-skill/skills/music-production/requirements.txt   # NumPy по хэшам
.venv/bin/python -m pip install scipy soundfile certifi matplotlib
export SSL_CERT_FILE=$(.venv/bin/python -c 'import certifi; print(certifi.where())')    # у Python с python.org нет корневых сертификатов
SK=music-skill/skills/music-production/scripts
.venv/bin/python $SK/bootstrap.py --system --runtime ~/.music-skill/.runtime --config ~/.music-skill/local-config.json
.venv/bin/python $SK/fetch_soundbanks.py --config ~/.music-skill/local-config.json --runtime ~/.music-skill/.runtime \
    --output ~/.music-skill/local-config.studio.json --only fsbs_clean,guitar_shiny,bass_darkblack,rusty,vcsl_world,bass_finger
.venv/bin/python $SK/studio.py doctor --config ~/.music-skill/local-config.studio.json
```

Объём: около 3 ГБ в `~/.music-skill/.runtime`. Это Surge XT 1.3.4 с каталогом пресетов, MS Basic и шесть банков. Все банки проверяются по SHA-256 из `soundbank-lock.json` skill.

Пути можно переопределить переменными `MUSIC_SKILL`, `MUSIC_SKILL_CONFIG`, `MUSIC_PY`, `MUSIC_WORK`.

## Сборка

```zsh
Tools/MusicGen/make_music.sh sketches          # три эскиза -> ArtSource/Audio/Music/sketches
Tools/MusicGen/make_music.sh theme             # тема -> ArtSource/Audio/Music/theme (игровой файл не трогается)
Tools/MusicGen/make_music.sh theme --install   # + заменить music_theme.wav в Resources
```

Рендер темы занимает около 20 с на M-серии. Каждый прогон пишет в новую папку `render-<время>` в `$MUSIC_WORK`, по умолчанию `$TMPDIR/scarbound-music`.

### Что совпадёт при повторе

- **Совпадёт:** ноты, исполнение (зерно `expression` фиксировано) и микс.
- **Не совпадёт побитово:** Surge XT запускает осцилляторы пэда со случайной фазой. Повторный синтез в новой папке даёт тот же звук, но другие сэмплы. Проверено: −16.96 LUFS в обоих случаях, true peak −1.12 и −1.35 dBTP.
- **Как получить точно ту версию, что сейчас в игре:** взять `ArtSource/Audio/Music/theme/scarbound_dust_road_groove_loop_44k_24bit.wav`.

## Где менять музыку

- **Ноты и форма.** `THEME_FORM`, `RIFF`, `BASS_A`, `CALL` и фразы, функция `theme()`.
- **Уровни партий.** `add_band()`, поле `level_dbfs` — опорный уровень партии. Автоматизация по секциям — в конце `theme()`.
- **Громкость мастера.** `mix_common(target=-17.0)`.
- **Мировая перкуссия.** Записана очень неровно: brake drum примерно на 35 dB громче тарелочек на той же velocity. Поэтому её удары автоматически разводятся по четырём партиям со своими уровнями: `PERC_PART`, `PERC_VEL`, `PERC_MIX`.

## Проверки после изменения

```zsh
~/.music-skill/.venv/bin/python Tools/MusicGen/measure.py Assets/RoadGame/Resources/Audio/music_theme.wav --loop
~/.music-skill/.venv/bin/python Tools/MusicGen/measure.py <файл> --gain-db -7.01   # уровень в игре: громкость источника 0.446
```

Unity — только в batch-режиме, с `-disableaudio`, в клоне проекта (см. `AGENTS.md`). `WorkAudioMute.cs` не трогать.
