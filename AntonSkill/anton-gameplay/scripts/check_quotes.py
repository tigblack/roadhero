#!/usr/bin/env python3
"""Сверка цитат Антона в отчёте с конспектами.
Цитатой Антона считается «…», за которой в той же строке идёт [чч:мм:сс] (или перед которой стоит «Антон»).
Каждый её фрагмент (части между «…») должен дословно найтись в конспектах, а хотя бы один тайм-код
из скобок — рядом с этим фрагментом в конспекте. Тексты игры в «» без тайм-кода не проверяются.
Запуск: python check_quotes.py <файл.md> [ещё файлы] — печатает только расхождения."""
import re, sys, pathlib

for s in (sys.stdout, sys.stderr):
    try:
        s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

ROOT = pathlib.Path(__file__).resolve().parents[1]          # папка скилла
SRC = [ROOT / "references" / n for n in ("СОВЕТЫ_АНТОНА.md", "UX_СОВЕТЫ_АНТОНА.md")]
TC = re.compile(r"\d\d:\d\d:\d\d")
BR = re.compile(r"\[([^\]\n]*\d\d:\d\d:\d\d[^\]\n]*)\]")      # [00:01:48], [00:41:45–00:42:07, 01:42:00]


def norm(s):
    return re.sub(r"\s+", " ", s.lower().replace("ё", "е")).strip()


src_lines = []
for p in SRC:
    src_lines += [norm(l) for l in p.read_text(encoding="utf-8").splitlines()]
src = "\n".join(src_lines)
src_times = set(TC.findall(src))


def near_times(frag):
    """Тайм-коды в строках конспекта, где есть фрагмент, и в двух строках вокруг."""
    out = set()
    for i, l in enumerate(src_lines):
        if frag in l:
            for j in range(max(0, i - 2), min(len(src_lines), i + 3)):
                out |= set(TC.findall(src_lines[j]))
    return out


bad = 0
for fn in sys.argv[1:]:
    text = pathlib.Path(fn).read_text(encoding="utf-8")
    for m in re.finditer(r"«([^»\n]{8,})»", text):
        after = re.match(r"[^«\n]{0,60}?\[([^\]\n]*\d\d:\d\d:\d\d[^\]\n]*)\]", text[m.end():])
        anton = re.search(r"Антон\w*[^«\n]{0,25}$", text[max(0, m.start() - 40):m.start()])
        if not after and not anton:
            continue                                         # текст игры или свой ярлык, не цитата
        q = m.group(1)
        ln = text.count("\n", 0, m.start()) + 1
        frags = [norm(f).strip(" .,:;!?—-") for f in q.split("…")]
        frags = [f for f in frags if len(f) >= 6]
        missing = [f for f in frags if f not in src]
        for f in missing:
            bad += 1
            print(f"{fn}:{ln}: цитаты нет в конспектах: «{f}»")
        if not after:
            bad += 1
            print(f"{fn}:{ln}: у цитаты Антона нет [тайм-кода]: «{q[:60]}»")
        elif frags and not missing:
            times = set(TC.findall(after.group(1)))
            if not any(times & near_times(f) for f in frags):
                bad += 1
                print(f"{fn}:{ln}: цитата есть, но в конспекте рядом с ней другой тайм-код: «{q[:50]}» [{after.group(1)}]")
    for m in BR.finditer(text):
        for t in TC.findall(m.group(1)):
            if t not in src_times:
                bad += 1
                ln = text.count("\n", 0, m.start()) + 1
                print(f"{fn}:{ln}: тайм-кода нет в конспектах: {t}")
print("расхождений:", bad)
sys.exit(1 if bad else 0)
