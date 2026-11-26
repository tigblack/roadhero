#!/usr/bin/env python
"""Геймплей игры -> листы кадров для разбора по Антону.

Нужно: Python 3.10+ с пакетами yt-dlp, pillow, numpy (python -m pip install -U yt-dlp pillow numpy),
ffmpeg 5.1+ в PATH и Node.js или Deno: без JS-движка YouTube отдаёт не все форматы.
Запуск из рабочей папки (корня проекта):
  python <папка скилла>/scripts/grab.py <команда> ...

  search "<запрос>" [-n 8]
      ролики YouTube: длительность | просмотры | канал | название | ссылка
  get <ссылка|файл> --name <имя> [--from 0] [--to 15:00] [--every N]
      скачать ролик и нарезать листы кадров. Без --every: первая минута — кадр в секунду,
      до 5-й минуты — раз в 3 с, дальше ~75 кадров до --to
  frame <имя> <время> [<время> ...] [--crop x,y,w,h]
      кадр целиком; --crop — увеличенный кусок, доли кадра 0..1 от левого верхнего угла

Результат лежит в _anton/<имя>/ в рабочей папке:
  sheets/NN_ммсс-ммсс.webp — листы по 12 кадров, над каждым кадром его время в ролике
  frames/*.webp            — отдельные кадры
  index.md, info.json      — что за ролик и что разобрано
Сам ролик лежит в кэше (Windows: %LOCALAPPDATA%\\anton-gameplay\\<имя>\\, иначе ~/.cache/anton-gameplay/<имя>/)
и через 7 дней удаляется.
"""
import argparse, json, math, os, re, shutil, subprocess, sys, time
from pathlib import Path

ROOT = Path.cwd()                                   # рабочая папка: результат ляжет в её _anton/
OUT = ROOT / "_anton"
CACHE = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".cache") / "anton-gameplay"
# без JS-движка YouTube отдаёт не все форматы. Deno yt-dlp находит сам, node надо назвать явно
BASE = [sys.executable, "-m", "yt_dlp", "--no-playlist", "--encoding", "utf-8"]
YTDLP = BASE + ([] if shutil.which("deno") or not shutil.which("node") else ["--js-runtimes", "node"])
LOW = getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0)   # не мешать работе за компьютером (Windows)
ENV = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
GAP, STRIP = 4, 22                                   # зазор между кадрами и полоса со временем над кадром

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def die(msg):
    print("ОШИБКА: " + msg)
    sys.exit(1)


def need_pkgs(*mods):
    for m in mods:
        try:
            __import__(m)
        except ImportError:
            die(f"нет пакета Python {m}: python -m pip install -U pillow numpy")


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=ENV, creationflags=LOW)
    except FileNotFoundError:
        die(f"не найдена программа {cmd[0]}: поставь её и добавь в PATH")


def ytdlp(args):
    for attempt in range(2):
        r = run(YTDLP + args)
        if "no such option" in r.stderr and "--js-runtimes" in r.stderr:     # старый yt-dlp
            r = run(BASE + args)
        if "not a bot" not in r.stderr or attempt:
            return r
        time.sleep(5)                      # проверка на бота у YouTube плавает, со второго раза обычно проходит


def why(r):
    if "not a bot" in r.stderr:
        return "YouTube просит подтвердить, что это не бот: повтори через пару минут или возьми другой ролик"
    if "No module named yt_dlp" in r.stderr:
        return "нет yt-dlp: python -m pip install -U yt-dlp"
    return r.stderr[-800:]


def secs(s):
    """'83', '83.5', '1:23', '1:02:03', '15m' -> секунды."""
    s = str(s).strip().lower()
    if s.endswith("m"):
        return float(s[:-1]) * 60
    t = 0.0
    for part in s.rstrip("s").split(":"):
        t = t * 60 + float(part)
    return t


def hms(t):
    t = int(round(t or 0))
    h, r = divmod(t, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def tag(t):
    t = int(t)
    return f"{t // 60:02d}{t % 60:02d}"


def slug(s):
    s = re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:40].strip("-")
    return s or "video"


# ---------- поиск и скачивание ----------

def cmd_search(a):
    r = ytdlp(["--flat-playlist", "--print", "%(id)s\t%(duration)s\t%(view_count)s\t%(channel)s\t%(title)s",
               f"ytsearch{a.n}:{a.query}"])
    rows = [l.split("\t", 4) for l in r.stdout.splitlines() if l.count("\t") >= 4]
    if not rows:
        die("поиск ничего не вернул\n" + why(r))
    for i, (vid, dur, views, ch, title) in enumerate(rows, 1):
        d = hms(float(dur)) if re.fullmatch(r"[\d.]+", dur) else "?"
        v = int(views) if views.isdigit() else 0
        v = f"{v / 1e6:.1f}M" if v >= 1e6 else f"{v // 1000}K" if v >= 1000 else str(v)
        print(f"{i}. {d:>7} | {v:>6} | {ch[:24]} | {title[:90]} | https://youtu.be/{vid}")


def url_info(url):
    r = ytdlp(["-J", "--flat-playlist", url])
    try:
        meta = json.loads(r.stdout)
    except ValueError:
        die("yt-dlp не открыл ссылку (приватный ролик, возраст, вход?) — возьми другой ролик\n" + why(r))
    if meta.get("_type") == "playlist":
        die("это плейлист или канал — нужна ссылка на один ролик")
    return meta


def download(url, dst, upto):
    """Только видео, до 1080p: мелкий текст интерфейса должен читаться. upto — скачать начало
    до этой секунды (None — целиком)."""
    shutil.rmtree(dst, ignore_errors=True)
    dst.mkdir(parents=True)
    args = ["-f", "bv*/b", "-S", "res:1080,vcodec:h264", "-I", "1", "--no-part", "--quiet", "--no-progress",
            "-o", str(dst / "video.%(ext)s")]
    if upto:
        args += ["--download-sections", f"*0-{int(upto)}"]
    r = ytdlp(args + [url])
    got = sorted(p for p in dst.glob("video.*") if p.suffix not in (".part", ".ytdl", ".json"))
    if not got:
        die("ролик не скачался\n" + why(r))
    return got[0]


def probe(video):
    r = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
             "stream=width,height:stream_side_data=rotation:stream_tags=rotate:format=duration",
             "-of", "json", str(video)])
    j = json.loads(r.stdout or "{}")
    st = (j.get("streams") or [{}])[0]
    w, h = st.get("width") or 0, st.get("height") or 0
    rot = 0
    for sd in st.get("side_data_list") or []:
        rot = int(sd.get("rotation", rot) or 0)
    rot = rot or int((st.get("tags") or {}).get("rotate", 0) or 0)
    if abs(rot) % 180 == 90:                         # ffmpeg сам поворачивает кадры при декодировании
        w, h = h, w
    if not w or not h:
        die("ffprobe не видит видео в файле")
    return w, h, float((j.get("format") or {}).get("duration") or 0)


def game_area(video, a, b, w, h):
    """Где на кадре сама игра. Вертикальную игру в горизонтальном ролике обычно ставят по центру,
    а по бокам чёрные поля или размытая копия; у них почти нет мелких деталей. Вернёт 'w:h:x:y' или None."""
    import numpy as np
    fw, fh = 640, max(2, round(640 * h / w / 2) * 2)
    step = max(2.0, (b - a) / 60)
    sel = f"select='isnan(prev_selected_t)+gte(t-prev_selected_t,{step:g})'"
    r = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-skip_frame", "nokey",
                        "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(video),
                        "-vf", f"{sel},scale={fw}:{fh},format=gray", "-fps_mode", "vfr",
                        "-pix_fmt", "gray", "-f", "rawvideo", "-"], capture_output=True, creationflags=LOW)
    n = len(r.stdout) // (fw * fh)
    if n < 3:
        return None
    A = np.frombuffer(r.stdout, np.uint8, n * fw * fh).reshape(n, fh, fw).astype(np.float32)
    # резкость столбца и строки: средняя |вторая разность| яркости по всем кадрам
    px = np.abs(A[:, :, 2:] - 2 * A[:, :, 1:-1] + A[:, :, :-2]).mean(axis=(0, 1))
    x0, x1 = span(np.pad(px, 1, mode="edge"))
    py = np.abs(A[:, 2:, x0:x1] - 2 * A[:, 1:-1, x0:x1] + A[:, :-2, x0:x1]).mean(axis=(0, 2))
    y0, y1 = span(np.pad(py, 1, mode="edge"))
    if (x0, x1, y0, y1) == (0, fw, 0, fh):
        return None
    kx, ky = w / fw, h / fh
    cx, cy = math.ceil(x0 * kx / 2) * 2, math.ceil(y0 * ky / 2) * 2
    cw, ch = int((x1 - x0) * kx) // 2 * 2, int((y1 - y0) * ky) // 2 * 2
    return f"{cw}:{ch}:{cx}:{cy}"


def span(p, run=8):
    """Отрезок с игрой вокруг середины профиля резкости p: края — первые `run` подряд «пустых» точек
    (резкость меньше четверти серединной). (0, len) — полей нет или они подозрительные."""
    import numpy as np
    n = len(p)
    low = p < 0.25 * float(np.median(p[int(n * 0.4):int(n * 0.6) + 1]))
    lo, hi, k = 0, n, 0
    for x in range(n // 2, -1, -1):
        k = k + 1 if low[x] else 0
        if k == run:
            lo = x + run
            break
    k = 0
    for x in range(n // 2, n):
        k = k + 1 if low[x] else 0
        if k == run:
            hi = x - run + 1
            break
    if (lo, hi) == (0, n) or hi - lo > 0.85 * n or hi - lo < 0.2 * n or abs(lo - (n - hi)) > 0.05 * n:
        return 0, n
    return lo + 1, hi - 1


# ---------- кадры и листы ----------

def plan(t0, t1, every):
    """[(начало, конец, шаг)]: первая минута подробно, до 5-й минуты чаще, дальше ~75 кадров."""
    if every:
        return [(t0, t1, every)]
    out = []
    for a, b, step in ((t0, t0 + 60, 1), (t0 + 60, t0 + 300, 3), (t0 + 300, t1, 0)):
        b = min(b, t1)
        if b - a >= 1:
            out.append((a, b, step or max(4, min(30, round((b - a) / 75)))))
    return out


def tiers_text(tiers):
    return ", ".join(f"{hms(a)}–{hms(b)} раз в {s:g} с" for a, b, s in tiers)


def layout(w, h):
    """Сетка листа на 12 кадров, при которой кадры крупнее всего на листе ~1360x860."""
    best = None
    for cols, rows in ((6, 2), (4, 3), (3, 4)):
        tw = min((1360 - (cols + 1) * GAP) / cols, ((860 - (rows + 1) * GAP) / rows - STRIP) * w / h)
        if not best or tw > best[0]:
            best = (tw, cols, rows)
    tw, cols, rows = best
    tw = int(tw) // 2 * 2
    return tw, int(tw * h / w) // 2 * 2, cols, rows


def grab(video, a, b, step, crop, tw, th, tmp):
    """Первый кадр каждого отрезка по step секунд на [a, b). Вернёт [(файл, время в ролике)].
    Время берётся из самого кадра (showinfo), а не из номера, поэтому подписи не врут."""
    tmp.mkdir(parents=True, exist_ok=True)
    sel = f"select='isnan(prev_selected_t)+gt(floor(t/{step:g}),floor(prev_selected_t/{step:g}))'"
    vf = ([f"crop={crop}"] if crop else []) + [sel, "showinfo", f"scale={tw}:{th}:flags=area"]
    r = run(["ffmpeg", "-hide_banner", "-nostats", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(video),
             "-vf", ",".join(vf), "-fps_mode", "vfr", "-q:v", "3", str(tmp / "%05d.jpg")])
    files = sorted(tmp.glob("*.jpg"))
    if not files:
        die(f"ffmpeg не достал кадры {hms(a)}–{hms(b)}\n" + r.stderr[-800:])
    times = [float(x) for x in re.findall(r"\bn:\s*\d+\s+pts:\s*-?\d+\s+pts_time:(\S+)", r.stderr)]
    if len(times) != len(files):
        times = [i * step for i in range(len(files))]
    return [(f, a + max(0.0, t)) for f, t in zip(files, times)]


def font(size):
    from PIL import ImageFont
    for name in ("arialbd.ttf", "arial.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            pass
    try:
        return ImageFont.load_default(size)               # Pillow 10.1+
    except Exception:
        return ImageFont.load_default()


def sheets(frames, tw, th, cols, rows, out):
    from PIL import Image, ImageDraw
    f = font(17)
    W = cols * tw + (cols + 1) * GAP
    H = rows * (th + STRIP) + (rows + 1) * GAP
    per, made = cols * rows, []
    for i in range(0, len(frames), per):
        chunk = frames[i:i + per]
        img = Image.new("RGB", (W, H), (34, 34, 34))
        d = ImageDraw.Draw(img)
        for k, (fp, t) in enumerate(chunk):
            x = GAP + (k % cols) * (tw + GAP)
            y = GAP + (k // cols) * (th + STRIP + GAP)
            d.text((x + 3, y + 1), hms(t), font=f, fill=(255, 220, 0))
            with Image.open(fp) as im:
                img.paste(im.convert("RGB").resize((tw, th)), (x, y + STRIP))
        name = f"{len(made) + 1:02d}_{tag(chunk[0][1])}-{tag(chunk[-1][1])}.webp"
        img.save(out / name, "WEBP", quality=80, method=4)
        made.append((name, chunk[0][1], chunk[-1][1]))
    return made


def write_index(d, info):
    lines = [f"# {info.get('title') or info['name']}", "",
             f"- источник: {info.get('url') or info['source']}",
             f"- канал: {info.get('channel') or '—'}",
             f"- ролик {hms(info['duration'])}, разобрано {hms(info['range'][0])}–{hms(info['range'][1])}",
             f"- кадры: {tiers_text(info['tiers'])}",
             f"- кадр игры {info['size'][0]}×{info['size'][1]}" + (", поля вокруг игры обрезаны" if info.get("crop") else ""),
             "", "## Листы: по 12 кадров, над кадром время в ролике", ""]
    lines += [f"- sheets/{p.name}" for p in sorted((d / "sheets").glob("*.webp"))]
    fr = sorted((d / "frames").glob("*.webp")) if (d / "frames").is_dir() else []
    if fr:
        lines += ["", "## Кадры", ""] + [f"- frames/{p.name}" for p in fr]
    (d / "index.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def cmd_get(a):
    need_pkgs("numpy", "PIL")
    src = a.source.strip().strip('"')
    name = slug(a.name)
    d = OUT / name
    old = json.loads((d / "info.json").read_text(encoding="utf-8")) if (d / "info.json").exists() else {}
    if old and old.get("source") != src:
        die(f"_anton/{name} уже занят другим роликом ({old.get('source')}) — дай другое --name")
    frm, to = secs(a.frm), secs(a.to)
    info = {"name": name, "source": src}
    if re.match(r"https?://", src):
        meta = url_info(src)
        dur = float(meta.get("duration") or 0)
        info.update(title=meta.get("title"), channel=meta.get("channel") or meta.get("uploader"),
                    url=meta.get("webpage_url") or src, duration=dur or None)
        # целиком быстрее: 10 минут ролика качаются ~40 с, а кусок через ffmpeg идёт почти в реальном времени.
        # Только начало — если ролик длиннее нужного куска в 7+ раз (длинные прохождения)
        need = to + 5 if dur and dur > 7 * (to + 5) else None
        video = Path(old.get("video") or "-")
        if video.is_file() and (not old.get("upto") or need and old["upto"] >= need):
            info["upto"] = old.get("upto")
        else:
            print(f"качаю «{info['title']}» ({hms(dur) if dur else '?'})"
                  + (f", первые {hms(need)}" if need else "") + " …", flush=True)
            video = download(src, CACHE / name, need)
            info["upto"] = need
    else:
        p = Path(src).expanduser()
        video = p if p.is_absolute() else ROOT / p
        if not video.is_file():
            die(f"нет файла {src}")
        info.update(title=video.stem, channel=None)

    w, h, vdur = probe(video)
    info["duration"] = info.get("duration") or vdur
    t1 = min(to, vdur) if vdur else to
    if frm >= t1:
        die(f"--from {hms(frm)} за концом ролика ({hms(vdur)})")
    crop = game_area(video, frm, t1, w, h)
    if crop:
        w, h = map(int, crop.split(":")[:2])
    tw, th, cols, rows = layout(w, h)
    tiers = plan(frm, t1, a.every)
    tmp = CACHE / name / "tmp"
    shutil.rmtree(tmp, ignore_errors=True)
    frames = []
    for i, (x, y, step) in enumerate(tiers):
        frames += grab(video, x, y, step, crop, tw, th, tmp / str(i))
    shutil.rmtree(d / "sheets", ignore_errors=True)
    (d / "sheets").mkdir(parents=True)
    made = sheets(frames, tw, th, cols, rows, d / "sheets")
    shutil.rmtree(tmp, ignore_errors=True)
    info.update(video=str(video), crop=crop, size=[w, h], range=[frm, t1], tiers=[list(t) for t in tiers])
    (d / "info.json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    write_index(d, info)
    cleanup()

    print(f"готово: «{info['title']}»" + (f", канал {info['channel']}" if info.get("channel") else ""))
    print(f"ролик {hms(info['duration'])}, разобрано {hms(frm)}–{hms(t1)}, кадр игры {w}×{h}"
          + (", поля вокруг игры обрезаны" if crop else ""))
    print(f"кадры: {tiers_text(tiers)}")
    print(f"_anton/{name}: листов {len(made)}, кадров {len(frames)}")
    for n, x, y in made:
        print(f"  sheets/{n}  {hms(x)}–{hms(y)}")


def cmd_frame(a):
    need_pkgs("PIL")
    from PIL import Image
    d = OUT / slug(a.name)
    if not (d / "info.json").exists():
        die(f"нет _anton/{d.name}: сначала get")
    info = json.loads((d / "info.json").read_text(encoding="utf-8"))
    video = Path(info["video"])
    if not video.is_file():
        die("ролика уже нет в кэше (он живёт 7 дней) — повтори get с той же ссылкой и тем же --name")
    box = [float(v) for v in a.crop.split(",")] if a.crop else None
    if box and (len(box) != 4 or min(box) < 0 or box[0] + box[2] > 1.001 or box[1] + box[3] > 1.001):
        die("--crop x,y,w,h — доли кадра от 0 до 1, например 0,0,1,0.15 (полоса сверху)")
    (d / "frames").mkdir(exist_ok=True)
    tmp = CACHE / d.name / "frame.jpg"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    for t in a.times:
        ts = secs(t)
        tmp.unlink(missing_ok=True)
        vf = ["-vf", f"crop={info['crop']}"] if info.get("crop") else []
        r = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{ts:.3f}", "-i", str(video),
                 "-frames:v", "1"] + vf + ["-q:v", "2", str(tmp)])
        if not tmp.exists():
            die(f"нет кадра на {hms(ts)}\n" + r.stderr[-500:])
        with Image.open(tmp) as im:
            im = im.convert("RGB")
        name = tag(ts) + (f".{int(ts * 10) % 10}" if ts % 1 >= 0.1 else "")
        if box:
            W, H = im.size
            im = im.crop((round(box[0] * W), round(box[1] * H), round((box[0] + box[2]) * W),
                          round((box[1] + box[3]) * H)))
            k = min(4.0, max(1.0, 1000 / max(im.size)))
            name += "_crop-" + "-".join(str(round(v * 100)) for v in box)
        else:
            k = min(1.0, 1600 / max(im.size))
        if k != 1:
            im = im.resize((round(im.width * k), round(im.height * k)), Image.LANCZOS)
        im.save(d / "frames" / f"{name}.webp", "WEBP", quality=90, method=4)
        print(f"_anton/{d.name}/frames/{name}.webp  ({hms(ts)})")
    tmp.unlink(missing_ok=True)
    write_index(d, info)


def cleanup():
    if CACHE.is_dir():
        old = time.time() - 7 * 86400
        for p in CACHE.iterdir():
            if p.is_dir() and p.stat().st_mtime < old:
                shutil.rmtree(p, ignore_errors=True)


def main():
    ap = argparse.ArgumentParser(description="Ролик геймплея -> листы кадров для разбора по Антону")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("search")
    s.add_argument("query")
    s.add_argument("-n", type=int, default=8)
    g = sub.add_parser("get")
    g.add_argument("source", help="ссылка (YouTube, Drive, TikTok, прямая) или видеофайл")
    g.add_argument("--name", required=True, help="имя папки латиницей, обычно по игре")
    g.add_argument("--from", dest="frm", default="0")
    g.add_argument("--to", default="15:00", help="до какого момента смотреть (по умолчанию 15:00)")
    g.add_argument("--every", type=float, default=0, help="один кадр раз в N секунд на всём отрезке")
    f = sub.add_parser("frame")
    f.add_argument("name")
    f.add_argument("times", nargs="+")
    f.add_argument("--crop", help="x,y,w,h долями кадра")
    a = ap.parse_args()
    {"search": cmd_search, "get": cmd_get, "frame": cmd_frame}[a.cmd](a)


if __name__ == "__main__":
    main()
