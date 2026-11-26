#!/usr/bin/env node
/**
 * Push pre-created, fast-forward Site source stages below the server's pack cap.
 * No commits, refs, working files, remotes, or Git configuration are created locally.
 *
 * Run in a retained TTY, then send one JSON line through hidden stdin:
 * { credential: <Sites credential>, source: <official source-opening result>,
 *   base: <full previous remote SHA>, commits: [<stage SHA>, ..., <final HEAD SHA>] }
 * Re-running the same input safely resumes a completed prefix of stages.
 * After success, use the official Sites workflow to package and verify final HEAD.
 */
import { spawn } from 'node:child_process';
import { existsSync, lstatSync, readFileSync, realpathSync } from 'node:fs';
import path from 'node:path';

let credential;
let checkout;
let activeChild;
let stopped = false;

function fail(message, code = 1) {
  const error = new Error(message);
  error.exitCode = code;
  throw error;
}

function redact(value) {
  let text = String(value || '');
  if (credential?.token) text = text.split(credential.token).join('[redacted]');
  return text.replace(/(Authorization:\s*Bearer\s+)\S+/gi, '$1[redacted]').slice(0, 6000);
}

async function readInput() {
  // Raw terminal mode disables echo before the readiness message is printed.
  const input = await new Promise((resolve, reject) => {
    let value = '';
    let finished = false;
    const terminal = Boolean(process.stdin.isTTY);
    const finish = (error) => {
      if (finished) return;
      finished = true;
      process.stdin.removeListener('data', onData);
      process.stdin.removeListener('end', onEnd);
      if (terminal) process.stdin.setRawMode(false);
      process.stdin.pause();
      error ? reject(error) : resolve(value);
    };
    const onData = (chunk) => {
      value += chunk;
      if (value.includes('\u0003')) finish(Object.assign(new Error('Stage push cancelled.'), { exitCode: 130 }));
      else if (value.length > 65536) finish(new Error('Input exceeds 64 KiB.'));
      else if (/[\r\n]/.test(value)) finish();
    };
    const onEnd = () => finish();
    if (terminal) process.stdin.setRawMode(true);
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', onData);
    process.stdin.once('end', onEnd);
    process.stderr.write('Ready for staged Site source JSON on stdin (input is hidden in a TTY).\n');
    process.stdin.resume();
  });
  try { return JSON.parse(input); } catch { fail('Provide one JSON object on stdin; input is never echoed.', 64); }
}

async function git(args, { network = false, check = true } = {}) {
  if (stopped) fail('Stage push interrupted.', 130);
  const env = { ...process.env, GIT_TERMINAL_PROMPT: '0' };
  // Never allow a trace to disclose ephemeral Authorization headers.
  for (const name of Object.keys(env)) {
    if (name.startsWith('GIT_TRACE') || name === 'GIT_CURL_VERBOSE') delete env[name];
  }
  delete env.SITES_GIT_AUTHORIZATION;
  delete env.SITES_STAGE_AUTHORIZATION;
  const auth = [];
  if (network) {
    auth.push('-c', 'credential.helper=', '-c', 'http.extraHeader=', '-c', 'http.followRedirects=false');
    if (credential.auth_mode === 'http_extra_header') {
      env.SITES_STAGE_AUTHORIZATION = `Authorization: Bearer ${credential.token}`;
      auth.push(`--config-env=http.${credential.remote_url}.extraHeader=SITES_STAGE_AUTHORIZATION`);
    }
  }
  const result = await new Promise((resolve) => {
    let stdout = '', stderr = '', launchError;
    const child = spawn('git', ['-C', checkout, ...auth, ...args], {
      env, stdio: ['ignore', 'pipe', 'pipe']
    });
    activeChild = child;
    child.stdout.on('data', (data) => { stdout += data; });
    child.stderr.on('data', (data) => { stderr += data; });
    child.once('error', () => { launchError = true; });
    child.once('close', (code, signal) => {
      if (activeChild === child) activeChild = undefined;
      resolve({ code: code ?? 1, signal, stdout, stderr: launchError ? 'Unable to start Git.' : stderr });
    });
  });
  if (result.signal || stopped) fail('Stage push interrupted; rerun the same input to verify and resume.', 130);
  if (check && result.code !== 0) fail(redact(result.stderr) || `Git operation failed (exit ${result.code}).`, result.code);
  return result;
}

async function main() {
  if (process.argv.length !== 2) fail('Pass inputs through stdin only; this script accepts no arguments.', 64);
  const request = await readInput();
  credential = request?.credential;
  const bearer = credential?.auth_mode === 'http_extra_header' && typeof credential.token === 'string' &&
    credential.token && !/[\r\n\0]/.test(credential.token);
  if (!(bearer || credential?.auth_mode === 'work_proxy')) fail('Use the returned Sites source credential.', 64);
  if (typeof credential.branch !== 'string' || !credential.branch || credential.branch.startsWith('-')) fail('Invalid source branch.', 64);
  let url;
  try { url = new URL(credential.remote_url); } catch { fail('Invalid source HTTPS URL.', 64); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || /[\r\n\0]/.test(credential.remote_url)) {
    fail('Use the returned HTTPS remote URL without embedded credentials, query, or fragment.', 64);
  }
  if (credential.token_expires_at && (!Number.isFinite(Date.parse(credential.token_expires_at)) || Date.parse(credential.token_expires_at) <= Date.now())) {
    fail('Renew the Sites source credential before pushing.', 64);
  }
  for (const name of ['GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE', 'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY', 'GIT_ALTERNATE_OBJECT_DIRECTORIES']) {
    if (process.env[name]) fail('Run without Git directory, index, or object-store overrides.', 64);
  }
  const source = request.source;
  if (!source?.project_id || !path.isAbsolute(source.checkout_path || '')) fail('Provide the official source-opening result.', 64);
  checkout = realpathSync(source.checkout_path);
  const gitEntry = path.join(checkout, '.git');
  if (!existsSync(gitEntry) || lstatSync(gitEntry).isSymbolicLink()) fail('The source checkout must retain its own Git metadata.');
  if (realpathSync((await git(['rev-parse', '--show-toplevel'])).stdout.trim()) !== checkout) fail('Git is not rooted at the selected source checkout.');
  const gitDirectory = (await git(['rev-parse', '--absolute-git-dir'])).stdout.trim();
  for (const marker of ['MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply']) {
    if (existsSync(path.join(gitDirectory, marker))) fail('Finish the existing Git operation before pushing stages.');
  }
  let hosting;
  try { hosting = JSON.parse(readFileSync(path.join(checkout, '.openai/hosting.json'), 'utf8')); } catch { fail('Invalid Site hosting manifest.'); }
  if (hosting.project_id !== source.project_id) fail('Source project ID does not match its hosting manifest.');
  const stages = request.commits;
  const isHash = (value) => typeof value === 'string' && /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(value);
  if (!isHash(request.base) || !Array.isArray(stages) || !stages.length || stages.length > 100 || !stages.every(isHash)) {
    fail('Provide a full base commit SHA and a nonempty array of full stage commit SHAs.', 64);
  }
  if (new Set([request.base, ...stages]).size !== stages.length + 1) fail('Base and stage commits must be distinct.', 64);
  const final = stages.at(-1);
  const assertStable = async () => {
    if ((await git(['rev-parse', 'HEAD'])).stdout.trim() !== final) fail('Local HEAD changed; no further stages will be pushed.');
    if ((await git(['status', '--porcelain'])).stdout.trim()) fail('Keep source working tree and index clean while pushing stages.');
  };
  await assertStable();
  let previous = request.base;
  for (const sha of [request.base, ...stages]) {
    if ((await git(['rev-parse', '--verify', `${sha}^{commit}`])).stdout.trim() !== sha) fail('Every supplied SHA must name a commit exactly.');
  }
  for (const sha of stages) {
    if ((await git(['merge-base', '--is-ancestor', previous, sha], { check: false })).code !== 0) fail('Every stage must descend from the preceding commit.');
    previous = sha;
  }
  const ref = `refs/heads/${credential.branch}`;
  await git(['check-ref-format', ref]);
  if ((await git(['ls-remote', '--get-url', credential.remote_url])).stdout.trim() !== credential.remote_url) fail('Source URL is affected by Git URL rewriting.');
  const rewrites = await git(['config', '--get-regexp', '^url\\..*\\.pushinsteadof$'], { check: false });
  if (rewrites.code > 1) fail('Unable to inspect Git URL rewriting.');
  if (rewrites.stdout.split('\n').some((line) => {
    const prefix = line.match(/^\S+\s+(.+)$/)?.[1];
    return prefix && credential.remote_url.startsWith(prefix);
  })) fail('Source push URL is affected by Git URL rewriting.');

  const proxyArgs = [];
  if (process.env.CODEX_NETWORK_PROXY_ACTIVE === '1' && process.env.HTTPS_PROXY) {
    const proxy = await git(['config', '--null', '--get-urlmatch', 'http.proxy', credential.remote_url], { check: false });
    if (proxy.code === 0 && proxy.stdout === '\0') proxyArgs.push(`--config-env=http.${credential.remote_url}.proxy=HTTPS_PROXY`);
  }
  const remote = (args) => git([...proxyArgs, ...args], { network: true });
  const remoteHead = async () => {
    const lines = (await remote(['ls-remote', '--heads', credential.remote_url, ref])).stdout.trim().split('\n').filter(Boolean);
    if (lines.length !== 1 || lines[0].split(/\s+/)[1] !== ref) fail('Expected source branch is missing or ambiguous.');
    return lines[0].split(/\s+/)[0];
  };
  const current = await remoteHead();
  const history = [request.base, ...stages];
  const completed = history.indexOf(current);
  if (completed < 0) fail('Remote HEAD differs from the expected base and staged commits; reconcile before retrying.');
  process.stdout.write(JSON.stringify({ status: 'validated', completedStages: completed, totalStages: stages.length, remote_sha: current }) + '\n');
  for (let index = completed; index < stages.length; index++) {
    await assertStable();
    const expected = history[index], next = stages[index];
    if (await remoteHead() !== expected) fail('Remote source changed before the next stage; no further push attempted.');
    // Every next commit was proved to descend from expected. The exact lease
    // supplies a compare-and-swap guard against a race after ls-remote; it never
    // permits overwriting an unexpected remote tip or an unrelated history.
    await remote(['push', '--porcelain', `--force-with-lease=${ref}:${expected}`, credential.remote_url, `${next}:${ref}`]);
    if (await remoteHead() !== next) fail('Remote HEAD did not match the completed stage; stop and inspect before retrying.');
    process.stdout.write(JSON.stringify({ status: 'pushed', stage: index + 1, totalStages: stages.length, commit_sha: next }) + '\n');
  }
  await assertStable();
  if (await remoteHead() !== final) fail('Remote HEAD changed after stage pushes.');
  process.stdout.write(JSON.stringify({ status: 'complete', project_id: source.project_id, commit_sha: final, stages: stages.length }) + '\n');
}

for (const signal of ['SIGINT', 'SIGTERM', 'SIGHUP']) process.on(signal, () => {
  stopped = true;
  if (activeChild) activeChild.kill(signal);
  else {
    if (process.stdin.isTTY) process.stdin.setRawMode(false);
    process.exit(signal === 'SIGINT' ? 130 : 143);
  }
});
main().catch((error) => {
  process.stderr.write(redact(error.message) + '\n');
  process.exitCode = error.exitCode || 1;
});
