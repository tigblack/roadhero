#!/usr/bin/env python3
"""Copy a Unity WebGL build and split oversized compressed assets for static hosting."""
import argparse
import datetime
import gzip
import hashlib
import json
from pathlib import Path
import shutil

LIMIT = 24 * 1024 * 1024


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def prepare(source, destination, version):
    source, destination = source.resolve(), destination.resolve()
    if source == destination or source in destination.parents:
        raise ValueError('Output must be separate from the source build')
    if destination.exists():
        raise ValueError('Output already exists; choose a fresh output directory')
    html = (source / 'index.html').read_text()
    required = ['    playButton.onclick = () => {', 'createUnityInstance(canvas, config, (value) => {']
    if any(html.count(marker) != 1 for marker in required):
        raise ValueError('Unexpected Unity template; refusing an ambiguous bootstrap edit')
    shutil.copytree(source, destination)
    manifest = {'format': 1, 'maxPartBytes': LIMIT, 'files': {}}
    for path in sorted(destination.rglob('*')):
        if not path.is_file() or path.stat().st_size <= LIMIT:
            continue
        relative = path.relative_to(destination).as_posix()
        data = path.read_bytes()
        parts = []
        for index, offset in enumerate(range(0, len(data), LIMIT)):
            chunk = data[offset:offset + LIMIT]
            target = path.with_name(path.name + f'.part{index:03d}.bin')
            target.write_bytes(chunk)
            parts.append({'url': target.relative_to(destination).as_posix(), 'bytes': len(chunk), 'sha256': sha256(chunk)})
        rebuilt = b''.join((destination / part['url']).read_bytes() for part in parts)
        if rebuilt != data:
            raise ValueError('Chunk reassembly differs from Unity build')
        entry = {'bytes': len(data), 'sha256': sha256(data), 'parts': parts}
        if data[:2] == b'\x1f\x8b':
            unpacked = gzip.decompress(rebuilt)  # also verifies gzip CRC and length
            entry['uncompressedBytes'] = len(unpacked)
            entry['uncompressedSha256'] = sha256(unpacked)
        manifest['files'][relative] = entry
        path.unlink()
    loader = Path(__file__).with_name('chunked-data-loader.js').read_bytes()
    loader_name = 'chunked-data-loader.' + sha256(loader)[:16] + '.js'
    (destination / loader_name).write_bytes(loader)
    html = html.replace('  <script>', f'  <script src="{loader_name}"></script>\n  <script>', 1)
    bootstrap = '    const chunkManifest = ' + json.dumps(manifest, separators=(',', ':')) + ';\n'
    bootstrap += '    const startUnity = (onProgress) => RoadGameChunkedData.run(config, chunkManifest, () => createUnityInstance(canvas, config, onProgress));\n\n'
    html = html.replace(required[0], bootstrap + required[0])
    html = html.replace(required[1], 'startUnity((value) => {')
    (destination / 'index.html').write_text(html)
    (destination / 'chunk-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    info = {'version': version, 'builtAtUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'sourceBuild': source.name, 'delivery': 'hashed Unity gzip assets with streamed 24 MiB parts',
            'chunkedFiles': list(manifest['files']), 'chunkLoader': loader_name}
    (destination / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    files = [{'path': p.relative_to(destination).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha256(p.read_bytes())}
             for p in sorted(destination.rglob('*')) if p.is_file()]
    (destination / 'release-files.json').write_text(json.dumps({'version': version, 'files': files}, indent=2) + '\n')
    if any(p.stat().st_size > LIMIT for p in destination.rglob('*') if p.is_file()):
        raise ValueError('An oversized output asset remains')
    print(json.dumps({'output': str(destination), 'version': version, 'files': len(files) + 1,
                      'chunkedFiles': manifest['files'], 'maxOutputBytes': max(p.stat().st_size for p in destination.rglob('*') if p.is_file())}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    parser.add_argument('--version', required=True)
    args = parser.parse_args()
    prepare(args.source, args.destination, args.version)
