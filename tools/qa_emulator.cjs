const fs = require('fs');
const path = require('path');
const os = require('os');
const http = require('http');
const { spawn, execFile } = require('child_process');
const { promisify } = require('util');

const exec = promisify(execFile);
const NODE_MODULES = process.env.VELA_NODE_MODULES || 'D:/codex/2026-11-02/native-toolkit/node_modules';
const { VvdManager, VelaImageType, IVvdArchType } = require(path.join(NODE_MODULES, '@aiot-toolkit/emulator'));
const { getRunningAvdConfigByName } = require(path.join(NODE_MODULES, '@aiot-toolkit/emulator/lib/emulatorutil/running'));
const { createGrpcClient } = require(path.join(NODE_MODULES, '@aiot-toolkit/emulator/lib/vvd/grpc'));

const ROOT = path.resolve(__dirname, '..');
const QA_HOME = path.join(ROOT, '.qa');
const AVDS_HOME = path.join(QA_HOME, 'avds');
const EMU_HOME = path.join(QA_HOME, 'emu-home');
const SHOTS_DIR = path.join(QA_HOME, 'shots');
const SDK_HOME = process.env.WATCH_SDK_HOME || 'D:/codex/2026-11-02/vela-sdk';
const ADB_PATH = process.env.WATCH_ADB_PATH || path.join(NODE_MODULES, '@miwt/adb/bin/win/adb.exe');
const VVD_NAME = process.env.WATCH_VVD_NAME || 'GinkaRW5';
const PKG_NAME = 'com.antigravity.ginka.rw5';
const SERIAL_PORT = Number(process.env.WATCH_SERIAL_PORT || 5584);
const GRPC_PORT = Number(process.env.WATCH_GRPC_PORT || 8584);
const DEBUG_PORT = Number(process.env.WATCH_DEBUG_PORT || 10084);
const CONTROL_PORT = Number(process.env.WATCH_CONTROL_PORT || 43196);

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function adbCmd(...args) {
  const r = await exec(ADB_PATH, ['-s', 'emulator-' + SERIAL_PORT, ...args], {
    windowsHide: true,
    timeout: 120000,
    maxBuffer: 1024 * 1024 * 8,
  });
  return (r.stdout || '') + (r.stderr || '');
}

function getScreenshot(agent) {
  return new Promise((resolve, reject) => {
    agent.client.getScreenshot(agent.controller.Image, agent.authMate, (err, res) => {
      if (err) return reject(err);
      if (!res || !res.image || !res.image.length) return reject(Error('Simulator screen not ready'));
      resolve(res.image);
    });
  });
}

async function main() {
  fs.mkdirSync(QA_HOME, { recursive: true });
  fs.mkdirSync(AVDS_HOME, { recursive: true });
  fs.mkdirSync(EMU_HOME, { recursive: true });
  fs.mkdirSync(SHOTS_DIR, { recursive: true });

  process.env.ANDROID_AVD_HOME = AVDS_HOME;
  process.env.ANDROID_EMULATOR_HOME = EMU_HOME;
  process.env.ANDROID_SDK_ROOT = SDK_HOME;
  process.env.CI = '1';

  const manager = new VvdManager({ sdkHome: SDK_HOME, vvdHome: AVDS_HOME });
  if (!manager.getVvdList().some((x) => x.name === VVD_NAME || x.vvdName === VVD_NAME)) {
    manager.createVvd({
      name: VVD_NAME,
      arch: IVvdArchType.arm,
      width: '432',
      height: '514',
      density: '320',
      shape: 'rect',
      flavor: 'watch',
      customLcdRadius: '34',
      imageType: VelaImageType.VELA_WATCH_5,
      imageDir: path.join(SDK_HOME, 'system-images/vela-watch-5.0'),
    });
  }
  const vvdDir = path.join(AVDS_HOME, VVD_NAME + '.vvd');
  const configIni = path.join(vvdDir, 'config.ini');
  if (fs.existsSync(configIni)) {
    fs.writeFileSync(configIni, fs.readFileSync(configIni, 'utf8').replace(/^hw\.ramSize=.*$/m, 'hw.ramSize=128'));
  }

  // Register VVD pointer in ~/.vela/vvd (Windows Vela emulator.exe lookup root)
  const regDir = path.join(os.homedir(), '.vela', 'vvd');
  fs.mkdirSync(regDir, { recursive: true });
  const regIni = path.join(regDir, VVD_NAME + '.ini');
  fs.writeFileSync(regIni, fs.readFileSync(path.join(AVDS_HOME, VVD_NAME + '.ini')));

  const rawCmd = await manager.getVvdStartCmd({
    vvdName: VVD_NAME,
    qtHideWindow: true,
    serialPort: SERIAL_PORT,
    grpcPort: GRPC_PORT,
    debugPort: DEBUG_PORT,
  });
  const args = rawCmd.split(' ').filter(Boolean);
  let binary = args.shift();
  if (!binary.endsWith('.exe')) binary += '.exe';
  const portIndex = args.indexOf('-port');
  if (portIndex >= 0) args.splice(portIndex + 1, 0, String(SERIAL_PORT));
  const qemuIndex = args.indexOf('-qemu');
  args.splice(qemuIndex < 0 ? args.length : qemuIndex, 0, '-memory', '128');

  const logPath = path.join(QA_HOME, 'emulator.log');
  const logStream = fs.createWriteStream(logPath, { flags: 'w' });
  let bootReady = false;
  let recentLog = '';

  console.log('Starting emulator:', binary, args.join(' '));
  const child = spawn(binary, args, {
    cwd: SDK_HOME,
    windowsHide: true,
    stdio: 'pipe',
    env: process.env,
  });

  function onData(chunk) {
    logStream.write(chunk);
    recentLog = (recentLog + chunk.toString('utf8')).slice(-8192);
    if (recentLog.includes('NuttShell (NSH)')) bootReady = true;
  }
  child.stdout.on('data', onData);
  child.stderr.on('data', onData);

  let agent = null;
  async function ensureGrpc() {
    if (agent) return agent;
    const conf = getRunningAvdConfigByName(VVD_NAME);
    if (!conf) throw Error('Running VVD config not found yet for ' + VVD_NAME);
    agent = createGrpcClient(conf);
    await agent.waitForReady();
    return agent;
  }

  let shuttingDown = false;
  async function cleanup() {
    if (shuttingDown) return;
    shuttingDown = true;
    try { await exec(ADB_PATH, ['-s', 'emulator-' + SERIAL_PORT, 'shell', 'poweroff'], { windowsHide: true, timeout: 5000 }); } catch {}
    await sleep(800);
    try { child.kill('SIGKILL'); } catch {}
    try { if (fs.existsSync(regIni)) fs.unlinkSync(regIni); } catch {}
    logStream.end();
  }

  const server = http.createServer(async (req, res) => {
    try {
      const url = new URL(req.url, 'http://127.0.0.1');
      let out = null;
      if (url.pathname === '/') {
        const html = fs.readFileSync(path.join(__dirname, 'emulator-view.html'), 'utf8');
        res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        res.end(html);
        return;
      } else if (url.pathname === '/info') {
        out = { name: VVD_NAME, packageName: PKG_NAME, bootReady, port: CONTROL_PORT };
      } else if (url.pathname === '/status') {
        out = { bootReady, grpcReady: !!getRunningAvdConfigByName(VVD_NAME), pid: child.pid };
      } else if (url.pathname === '/screen') {
        if (!bootReady) {
          res.writeHead(503, { 'Content-Type': 'application/json' });
          res.end(JSON.stringify({ error: 'booting' }));
          return;
        }
        const a = await ensureGrpc();
        const png = await getScreenshot(a);
        const saveAs = url.searchParams.get('out');
        if (saveAs) fs.writeFileSync(path.resolve(SHOTS_DIR, saveAs), png);
        res.writeHead(200, { 'Content-Type': 'image/png' });
        res.end(png);
        return;
      } else if (url.pathname === '/tap' || url.pathname === '/click') {
        const a = await ensureGrpc();
        const x = Number(url.searchParams.get('x'));
        const y = Number(url.searchParams.get('y'));
        a.sendMouse({ x, y, buttons: 1 });
        await sleep(90);
        a.sendMouse({ x, y, buttons: 0 });
        out = { tapped: [x, y] };
      } else if (url.pathname === '/longpress') {
        const a = await ensureGrpc();
        const x = Number(url.searchParams.get('x'));
        const y = Number(url.searchParams.get('y'));
        const holdMs = Math.max(550, Math.min(2000, Number(url.searchParams.get('ms') || 700)));
        a.sendMouse({ x, y, buttons: 1 });
        await sleep(holdMs);
        a.sendMouse({ x, y, buttons: 0 });
        out = { longPressed: [x, y], ms: holdMs };
      } else if (url.pathname === '/drag') {
        const a = await ensureGrpc();
        const x0 = Number(url.searchParams.get('x0'));
        const y0 = Number(url.searchParams.get('y0'));
        const x1 = Number(url.searchParams.get('x1'));
        const y1 = Number(url.searchParams.get('y1'));
        for (let i = 0; i <= 15; i++) {
          a.sendMouse({ x: Math.round(x0 + (x1 - x0) * i / 15), y: Math.round(y0 + (y1 - y0) * i / 15), buttons: 1 });
          await sleep(20);
        }
        a.sendMouse({ x: x1, y: y1, buttons: 0 });
        out = { dragged: [[x0, y0], [x1, y1]] };
      } else if (url.pathname === '/wake') {
        const a = await ensureGrpc();
        a.sendKey({ key: 'Power', eventType: 2 });
        out = 'woke';
      } else if (url.pathname === '/install') {
        const rpk = path.resolve(url.searchParams.get('rpk'));
        const target = '/data/ginka-test.rpk';
        await adbCmd('wait-for-device');
        const pushOut = await adbCmd('push', rpk, target);
        const instOut = await adbCmd('shell', 'pm', 'install', target);
        if (!/success 0|Success/i.test(instOut)) throw Error('Install failed: ' + instOut);
        await adbCmd('shell', 'rm', target).catch(() => {});
        const pkgInfo = await adbCmd('shell', 'pm', 'get', PKG_NAME);
        out = { pushOut: pushOut.trim(), instOut: instOut.trim(), pkgInfo: pkgInfo.trim() };
      } else if (url.pathname === '/start') {
        await adbCmd('wait-for-device');
        for (let i = 0; i < 60; i++) {
          const info = await adbCmd('shell', 'pm', 'get', PKG_NAME).catch(() => '');
          if (/bAllValid: true/.test(info)) {
            const startOut = await adbCmd('shell', 'am', 'start', PKG_NAME);
            if (!/execution error|failed/i.test(startOut)) {
              out = { startOut: startOut.trim() };
              break;
            }
          }
          await sleep(500);
        }
        if (!out) throw Error('Timed out waiting to start ' + PKG_NAME);
      } else if (url.pathname === '/stop') {
        out = (await adbCmd('shell', 'am', 'force-stop', PKG_NAME)).trim();
      } else if (url.pathname === '/logtail') {
        out = { log: fs.readFileSync(logPath, 'utf8').slice(-Number(url.searchParams.get('n') || 4000)) };
      } else if (url.pathname === '/shutdown') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        res.end(JSON.stringify({ stopping: true }));
        server.close();
        await cleanup();
        process.exit(0);
      } else {
        res.writeHead(404);
        res.end();
        return;
      }
      res.writeHead(200, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(out));
    } catch (e) {
      res.writeHead(500, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ error: e.message || String(e) }));
    }
  });

  server.listen(CONTROL_PORT, '127.0.0.1', () => {
    console.log('QA_CONTROL http://127.0.0.1:' + CONTROL_PORT);
  });

  child.on('exit', async (code) => {
    console.log('Emulator exited with code', code);
    try { if (fs.existsSync(regIni)) fs.unlinkSync(regIni); } catch {}
    server.close();
    logStream.end();
    process.exit(code || 0);
  });

  process.on('SIGINT', async () => { await cleanup(); process.exit(0); });
  process.on('SIGTERM', async () => { await cleanup(); process.exit(0); });
}

main().catch((e) => {
  console.error(e);
  process.exitCode = 1;
});
