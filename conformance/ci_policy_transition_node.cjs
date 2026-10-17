'use strict';

// Loaded only from the literal T bootstrap. Neither candidate code nor an
// artifact supplies this path, its digest, the helper, or the RPC endpoint.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const cp = require('node:child_process');
const http = require('node:http');
const https = require('node:https');
const dc = require('node:diagnostics_channel');
const {StringDecoder} = require('node:string_decoder');
const originalSpawn = cp.spawn;
const originalSpawnSync = cp.spawnSync;
const directory = process.env.OFARM_TRANSITION_TOOLS_DIRECTORY;
let sequence = 0;
let requestSequence = 0;
let closed = false;
let terminal = false;
const processId = crypto.randomUUID();
const pending = new Map();
const children = new Set();

function terminate(reason = 'supervisor-refusal') {
  if (terminal) process.exit(86);
  terminal = true;
  for (const child of children) child.kill('SIGTERM');
  // Refusal is permanent. Settle only bytes already observed before exiting;
  // these incomplete dispositions can never turn a failed run into evidence.
  // A missing ACK is not retried: the supervisor may already have charged it.
  if (helper && helperEnvironment.OFARM_TRANSITION_TOOLS_NONCE && !closed) {
    for (const [requestId, record] of pending) {
      pending.delete(requestId);
      exchange('end', {requestId, bytes: record.bytes, complete: false});
    }
    exchange('fatal', {reason});
  }
  process.exit(86);
}

function exactFile(filename, digest) {
  const stat = fs.lstatSync(filename);
  if (!stat.isFile() || stat.isSymbolicLink() || stat.uid !== process.getuid()
      || (stat.mode & 0o022) || !/^[a-f0-9]{64}$/.test(digest || '')
      || crypto.createHash('sha256').update(fs.readFileSync(filename)).digest('hex') !== digest) {
    throw new Error('bootstrap-file');
  }
}

const forbiddenEnvironment = ['HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
  'http_proxy', 'https_proxy', 'all_proxy', 'no_proxy', 'NODE_PATH',
  'NODE_EXTRA_CA_CERTS', 'NODE_TLS_REJECT_UNAUTHORIZED', 'SSL_CERT_FILE', 'SSL_CERT_DIR',
  'GIT_SSL_CAINFO', 'GIT_SSL_CAPATH', 'GIT_SSL_NO_VERIFY'];
let helper;
const helperEnvironment = {PATH: '/usr/bin:/bin', LANG: 'C.UTF-8'};
try {
  for (const key of forbiddenEnvironment) {
    if (process.env[key]) throw new Error('ambient-transport-override');
    delete process.env[key];
  }
  if (!directory || !path.isAbsolute(directory)
      || fs.realpathSync(directory) !== directory) throw new Error('directory');
  const stat = fs.statSync(directory);
  if (!stat.isDirectory() || stat.uid !== process.getuid() || (stat.mode & 0o777) !== 0o700) {
    throw new Error('custody');
  }
  helper = path.join(directory, 'tools.py');
  if (process.env.OFARM_TRANSITION_TOOLS_SUPERVISOR !== helper
      || __filename !== path.join(directory, 'node.cjs')
      || process.env.NODE_OPTIONS !== `--require=${__filename}`) throw new Error('selection');
  exactFile(__filename, process.env.OFARM_TRANSITION_NODE_SHA256);
  exactFile(helper, process.env.OFARM_TRANSITION_TOOLS_SHA256);
  for (const name of ['OFARM_TRANSITION_TOOLS_DIRECTORY', 'OFARM_TRANSITION_TOOLS_NONCE',
    'OFARM_TRANSITION_TOOLS_JOB', 'OFARM_TRANSITION_TOOLS_SUPERVISOR']) {
    if (!process.env[name]) throw new Error('binding');
    helperEnvironment[name] = process.env[name];
  }
  helperEnvironment.HOME = directory;
} catch {
  terminate();
}

function exchange(operation, fields = {}) {
  const frame = {schema: 1, nonce: helperEnvironment.OFARM_TRANSITION_TOOLS_NONCE,
    processId, sequence: sequence++, operation, ...fields};
  const result = Reflect.apply(originalSpawnSync, cp, ['/usr/bin/python3', ['-I', '-S', helper, 'rpc'], {
    env: helperEnvironment, input: JSON.stringify(frame) + '\n', encoding: 'utf8',
    timeout: 10000, maxBuffer: 4096, windowsHide: true,
  }]);
  try {
    if (result.error || result.signal || result.status !== 0 || result.stderr) throw new Error();
    const ack = JSON.parse(result.stdout);
    if (ack.accepted !== true || ack.sequence !== frame.sequence) throw new Error();
    return true;
  } catch {
    return false;
  }
}

function rpc(operation, fields = {}) {
  if (terminal || closed || !exchange(operation, fields)) terminate();
}

function fatal(reason) {
  terminate(reason);
}

rpc('open', {kind: 'node', pid: process.pid, ppid: process.ppid});

function target(method, input, transport) {
  let url;
  try { url = new URL(input); } catch { fatal('unknown-route'); }
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password
      || !/^(GET|HEAD|POST|PUT|DELETE|PATCH|OPTIONS)$/.test(method)
      || /[\u0000-\u0020\u007f]/.test(url.pathname)) fatal('unknown-route');
  const host = (url.host + (url.protocol === 'http:' && !url.port ? ':80' : '')).toLowerCase();
  let bucket;
  if (transport === 'git') bucket = 'Git';
  else if (url.hostname === 'api.github.com') bucket = url.pathname === '/graphql' ? 'GraphQL' : 'REST';
  else if (url.hostname.endsWith('.blob.core.windows.net')) bucket = 'blob';
  else if (url.hostname.endsWith('.actions.githubusercontent.com')) bucket = 'runtime';
  else bucket = 'download'; // Supervisor owns the closed host/path allowlist.
  return {method, host, path: url.pathname, bucket};
}

function begin(metadata) {
  const requestId = `${processId}:${++requestSequence}`;
  pending.set(requestId, {bytes: 0, response: false});
  rpc('begin', {requestId, ...metadata});
  return requestId;
}

function quota(headers) {
  const values = {};
  if (Array.isArray(headers)) {
    for (let i = 0; i < headers.length; i += 2) {
      const name = String(headers[i]).toLowerCase();
      if (name.startsWith('x-ratelimit-')) values[name] = String(headers[i + 1]);
    }
  } else {
    for (const name of ['x-ratelimit-limit', 'x-ratelimit-remaining', 'x-ratelimit-reset', 'x-ratelimit-resource', 'x-ratelimit-used']) {
      if (headers[name] !== undefined) values[name] = String(headers[name]);
    }
  }
  const names = ['limit', 'remaining', 'reset', 'used'];
  if (!Object.keys(values).length) return null;
  const result = {};
  for (const name of names) {
    const value = values[`x-ratelimit-${name}`];
    if (!/^\d+$/.test(value || '') || !Number.isSafeInteger(Number(value))) fatal('unknown-quota');
    result[name] = Number(value);
  }
  if (!['core', 'graphql'].includes(values['x-ratelimit-resource'])) fatal('unknown-quota');
  result.bucket = values['x-ratelimit-resource'] === 'core' ? 'REST' : 'GraphQL';
  return result;
}

function response(requestId, status, headers = {}) {
  const record = pending.get(requestId);
  if (!record || record.response || !Number.isInteger(status) || status < 200 || status > 599) {
    fatal('unknown-response');
  }
  record.response = true;
  rpc('response', {requestId, status, quota: quota(headers)});
  if (status === 403 || status === 429) fatal('throttle');
}

function bytes(requestId, count) {
  const record = pending.get(requestId);
  if (!record || !Number.isSafeInteger(count) || count < 0) fatal('unknown-response');
  record.bytes += count;
  if (!Number.isSafeInteger(record.bytes)) fatal('byte-limit');
}

function end(requestId) {
  const record = pending.get(requestId);
  if (!record || !record.response) fatal('incomplete-response');
  pending.delete(requestId);
  rpc('end', {requestId, bytes: record.bytes, complete: true});
}

for (const [module, protocol] of [[http, 'http:'], [https, 'https:']]) {
  const request = module.request;
  module.request = function (...args) {
    let options;
    if (typeof args[0] === 'string' || args[0] instanceof URL) {
      const url = new URL(args[0]);
      options = {protocol: url.protocol, hostname: url.hostname, port: url.port,
        path: url.pathname + url.search, ...(typeof args[1] === 'object' ? args[1] : {})};
    } else options = {...args[0]};
    if (options.socketPath || options.createConnection) fatal('unknown-transport');
    const authority = options.hostname || options.host || 'localhost';
    const port = options.port ? `:${options.port}` : '';
    const id = begin(target((options.method || 'GET').toUpperCase(),
      `${options.protocol || protocol}//${authority}${port}${options.path || '/'}`, 'node'));
    let req;
    try { req = Reflect.apply(request, this, args); } catch { fatal('transport-error'); }
    let sent = false;
    const write = req.write;
    const finish = req.end;
    function count(chunk, encoding) {
      if (chunk !== undefined && chunk !== null && typeof chunk !== 'function') {
        // Count bytes offered to the transport even when it fails before its
        // finish event. This is conservative and never credits an abort.
        bytes(id, typeof chunk === 'string' ? Buffer.byteLength(chunk, typeof encoding === 'string' ? encoding : undefined) : chunk.length);
      }
    }
    req.write = function (...values) { count(values[0], values[1]); return Reflect.apply(write, this, values); };
    req.end = function (...values) { count(values[0], values[1]); return Reflect.apply(finish, this, values); };
    req.once('finish', () => { sent = true; });
    req.prependOnceListener('response', res => {
      response(id, res.statusCode, res.headers);
      const push = res.push;
      res.push = function (chunk, encoding) {
        if (chunk !== null) bytes(id, typeof chunk === 'string' ? Buffer.byteLength(chunk, encoding) : chunk.length);
        return Reflect.apply(push, this, [chunk, encoding]);
      };
      res.once('end', () => { if (!sent) fatal('incomplete-request'); end(id); });
      res.once('aborted', () => fatal('incomplete-response'));
      res.once('error', () => fatal('transport-error'));
      res.once('close', () => { if (pending.has(id)) fatal('incomplete-response'); });
    });
    req.once('upgrade', () => fatal('unknown-transport'));
    req.once('connect', () => fatal('unknown-transport'));
    req.once('error', () => fatal('transport-error'));
    return req;
  };
  module.get = function (...args) { const req = module.request(...args); req.end(); return req; };
}

// Bundled Undici uses its own transport. Observe its actual request object and
// count delivered body chunks without copying, replacing, or logging content.
const undici = new WeakMap();
dc.channel('undici:request:create').subscribe(({request}) => {
  if (typeof request.onData !== 'function') fatal('unknown-transport');
  const id = begin(target(request.method, new URL(request.path, request.origin), 'node'));
  undici.set(request, id);
  if (typeof request.onBodySent !== 'function') fatal('unknown-transport');
  const onBodySent = request.onBodySent;
  request.onBodySent = function (chunk) {
    bytes(id, chunk.length);
    return Reflect.apply(onBodySent, this, [chunk]);
  };
  const onData = request.onData;
  request.onData = function (chunk) {
    bytes(id, chunk.length);
    return Reflect.apply(onData, this, [chunk]);
  };
});
dc.channel('undici:request:headers').subscribe(({request, response: res}) => {
  response(undici.get(request), res.statusCode, res.headers);
});
dc.channel('undici:request:trailers').subscribe(({request}) => {
  end(undici.get(request));
  undici.delete(request);
});
dc.channel('undici:request:error').subscribe(() => fatal('transport-error'));

cp.spawn = function (command, args, options) {
  if (path.basename(String(command)) !== 'git') {
    return Reflect.apply(originalSpawn, this, [command, args, options]);
  }
  if (!Array.isArray(args)) fatal('unknown-git-command');
  const env = {...(options?.env || process.env)};
  for (const key of Object.keys(env)) if (key.startsWith('GIT_TRACE')) delete env[key];
  env.GIT_TRACE_CURL = '3';
  env.GIT_TRACE_REDACT = '1';
  const stdio = options?.stdio === undefined ? ['pipe', 'pipe', 'pipe'] : options.stdio;
  if (!Array.isArray(stdio) || stdio.length !== 3) fatal('unknown-git-pipe');
  const child = Reflect.apply(originalSpawn, this, [command, args, {...options, env, stdio: [...stdio, 'pipe']}]);
  children.add(child);
  const decoder = new StringDecoder('utf8');
  let buffered = '';
  let current = null;
  let drained = false;
  let observed = 0;
  let gitHost = null;
  // Raw header/payload dump lines stay in this private pipe and are discarded.
  // Only direction-specific transfer counts and actual status framing are used.
  // An exact trace prefix prevents an attacker-controlled header containing a
  // structural marker from being interpreted as a status/request line.
  const prefix = '^\\d{2}:\\d{2}:\\d{2}\\.\\d+ [^\\r\\n]*?http\\.c:\\d+ +';
  const send = new RegExp(prefix + '=> Send header: (GET|POST|HEAD) ([^ ]+) HTTP/[0-9.]+$');
  const status = new RegExp(prefix + '<= Recv header: HTTP/[0-9.]+ ([0-9]{3})(?: |$)');
  const host = new RegExp(prefix + '=> Send header: [Hh]ost: ([a-zA-Z0-9.:-]+)$');
  const transferred = new RegExp(prefix + '(?:<= Recv|=> Send) data, ([0-9]+) bytes');
  let queued = null;
  function consume(line) {
    let match = line.match(send);
    if (match) {
      if (queued || (current && !pending.get(current)?.response)) fatal('missing-git-status');
      if (current) { end(current); current = null; }
      queued = {method: match[1], path: match[2]};
      return;
    }
    match = line.match(host);
    if (match && queued) {
      gitHost = match[1];
      current = begin(target(queued.method, `https://${gitHost}${queued.path}`, 'git'));
      observed += 1;
      queued = null;
      return;
    }
    match = line.match(status);
    if (match) {
      const code = Number(match[1]);
      if (code < 200) return;
      if (!current) fatal('missing-git-request');
      response(current, code);
      return;
    }
    match = line.match(transferred);
    if (match) {
      if (!current) fatal('missing-git-response');
      bytes(current, Number(match[1]));
    }
  }
  child.stdio[3].on('data', data => {
    buffered += decoder.write(data);
    let offset;
    while ((offset = buffered.indexOf('\n')) !== -1) {
      const line = buffered.slice(0, offset).replace(/\r$/, '');
      buffered = buffered.slice(offset + 1);
      consume(line);
    }
    if (buffered.length > 16384) fatal('trace-limit');
  });
  child.stdio[3].once('end', () => {
    buffered += decoder.end();
    if (buffered) consume(buffered.replace(/\r$/, ''));
    buffered = '';
    drained = true;
  });
  child.stdio[3].once('error', () => fatal('trace-error'));
  child.prependOnceListener('close', (code, signal) => {
    children.delete(child);
    if (!drained || queued || (current && !pending.get(current)?.response)) fatal('incomplete-git-trace');
    if (current) { end(current); current = null; }
    if (args.includes('fetch') && (code !== 0 || signal || !observed || !gitHost)) {
      fatal('failed-git-fetch');
    }
  });
  return child;
};

process.once('exit', code => {
  if (closed || terminal) return;
  if (code !== 0 || pending.size || children.size) fatal('incomplete-process');
  rpc('close');
  closed = true;
});
