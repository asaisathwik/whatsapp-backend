/**
 * WhatsApp Bridge Server — with crash recovery
 * Generates REAL scannable WhatsApp QR codes using whatsapp-web.js
 * Runs on port 8001
 */

const express = require("express");
const cors = require("cors");
const qrcode = require("qrcode");
const fs = require("fs");
const path = require("path");
const { Client, LocalAuth, MessageMedia } = require("whatsapp-web.js");

const app = express();
app.use(cors());
app.use(express.json());

const PORT = process.env.PORT || 8001;

const { execSync } = require("child_process");

// In-memory session store
const sessions = {};

// Clean stale Chromium locks that cause Puppeteer to stall on Windows
function cleanSessionLocks(instanceName) {
  try {
    // Kill any orphaned chrome processes matching this session
    try {
      execSync(
        `powershell -Command "Get-CimInstance Win32_Process -Filter \\"name = 'chrome.exe'\\" | Where-Object { $_.CommandLine -like '*session-${instanceName}*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"`,
        { stdio: "ignore", timeout: 3000 }
      );
    } catch {}

    const sessionDir = path.join(__dirname, "sessions", `session-${instanceName}`);
    if (fs.existsSync(sessionDir)) {
      const lockFiles = [
        "SingletonLock",
        "SingletonCookie",
        "SingletonSocket",
        "DevToolsActivePort",
        "lockfile",
        "first_party_sets.db-journal"
      ];
      for (const file of lockFiles) {
        const lockPath = path.join(sessionDir, file);
        if (fs.existsSync(lockPath)) {
          try {
            fs.unlinkSync(lockPath);
            console.log(`[${instanceName}] 🧹 Cleared stale lock: ${file}`);
          } catch {}
        }
        const defaultLockPath = path.join(sessionDir, "Default", file);
        if (fs.existsSync(defaultLockPath)) {
          try {
            fs.unlinkSync(defaultLockPath);
            console.log(`[${instanceName}] 🧹 Cleared stale default lock: ${file}`);
          } catch {}
        }
      }
    }
  } catch (err) {
    console.warn(`[${instanceName}] Lock cleanup notice:`, err.message);
  }
}

// ─── Puppeteer launch args ────────────────────────────────────────────────────
const PUPPETEER_ARGS = [
  "--no-sandbox",
  "--disable-setuid-sandbox",
  "--disable-dev-shm-usage",
  "--disable-accelerated-2d-canvas",
  "--no-first-run",
  "--no-zygote",
  "--disable-gpu",
  "--disable-extensions",
  "--disable-software-rasterizer",
  "--disable-background-networking",
  "--disable-default-apps",
  "--disable-sync",
  "--metrics-recording-only",
  "--mute-audio",
  "--no-default-browser-check",
];

// ─── Create / restart a WhatsApp client ──────────────────────────────────────
function createClient(instanceName, existingSession) {
  // Reuse existing session object or create a fresh one
  const session = existingSession || {
    name: instanceName,
    status: "INITIALIZING",
    qr_base64: null,
    qr_raw: null,
    phone: null,
    pushname: null,
    platform: "WhatsApp Web",
    createdAt: new Date().toISOString(),
    restarts: 0,
    client: null,
  };

  sessions[instanceName] = session;
  session.status = "INITIALIZING";
  session.qr_base64 = null;
  session.qr_raw = null;

  (async () => {
    // Destroy old client cleanly before recreating
    if (session.client) {
      try {
        console.log(`[${instanceName}] Closing existing Puppeteer instance...`);
        await session.client.destroy();
        await new Promise((r) => setTimeout(r, 800));
      } catch (e) {
        console.warn(`[${instanceName}] Client destroy notice:`, e.message);
      }
      session.client = null;
    }

    cleanSessionLocks(instanceName);

    const client = new Client({
      authStrategy: new LocalAuth({
        clientId: instanceName,
        dataPath: `./sessions`,
      }),
      puppeteer: {
        headless: true,
        handleSIGINT: false,
        handleSIGTERM: false,
        handleSIGHUP: false,
        args: PUPPETEER_ARGS,
      },
      authTimeoutMs: 90000,
      takeoverOnConflict: true,
      qrMaxRetries: 0,
    });

  session.client = client;

  // ── Loading screen ──────────────────────────────────────────────────────
  client.on("loading_screen", (percent, message) => {
    session.status = "LOADING";
    session.loading_percent = percent;
    session.loading_message = message;
    console.log(`[${instanceName}] Loading: ${percent}% - ${message}`);
  });

  // ── QR ──────────────────────────────────────────────────────────────────
  client.on("qr", async (qr) => {
    console.log(`[${instanceName}] QR received — generating image...`);
    session.status = "QR_READY";
    session.qr_raw = qr;
    session.qr_generated_at = Date.now();
    try {
      const dataUrl = await qrcode.toDataURL(qr, {
        errorCorrectionLevel: "M",
        type: "image/png",
        width: 360,
        margin: 1,
        color: { dark: "#0b141a", light: "#ffffff" },
      });
      session.qr_base64 = dataUrl;
      console.log(`[${instanceName}] QR ready (${dataUrl.length} bytes)`);
    } catch (err) {
      console.error(`[${instanceName}] QR image error:`, err.message);
    }
  });

  // ── Authenticated ────────────────────────────────────────────────────────
  client.on("authenticated", () => {
    console.log(`[${instanceName}] Authenticated ✓`);
    session.status = "AUTHENTICATED";
  });

  // ── Ready / Connected ────────────────────────────────────────────────────
  client.on("ready", () => {
    console.log(`[${instanceName}] ✅ WhatsApp CONNECTED!`);
    session.status = "CONNECTED";
    session.qr_base64 = null;
    session.qr_raw = null;
    try {
      session.phone = client.info?.wid?.user || null;
      session.pushname = client.info?.pushname || null;
      session.platform = client.info?.platform || "WhatsApp Web";
      console.log(`[${instanceName}] Phone: ${session.phone}, Name: ${session.pushname}`);
    } catch {}
  });

  // ── Auth failure ─────────────────────────────────────────────────────────
  client.on("auth_failure", (msg) => {
    console.error(`[${instanceName}] Auth failure: ${msg}`);
    session.status = "DISCONNECTED";
    session.qr_base64 = null;
  });

  // ── Disconnected ─────────────────────────────────────────────────────────
  client.on("disconnected", (reason) => {
    console.log(`[${instanceName}] Disconnected: ${reason}`);
    session.status = "DISCONNECTED";
    session.qr_base64 = null;
    session.qr_raw = null;

    if (reason === "LOGOUT") {
      console.log(`[${instanceName}] 🧹 Session logged out. Purging stale directory for fresh QR...`);
      try {
        const sessionDir = path.join(__dirname, "sessions", `session-${instanceName}`);
        if (fs.existsSync(sessionDir)) {
          fs.rmSync(sessionDir, { recursive: true, force: true });
        }
      } catch (e) {
        console.warn(`[${instanceName}] Purge notice:`, e.message);
      }
      setTimeout(() => createClient(instanceName, session), 2000);
    } else if (session.restarts < 8) {
      session.restarts++;
      console.log(`[${instanceName}] Reconnecting in 3s... (attempt ${session.restarts})`);
      setTimeout(() => createClient(instanceName, session), 3000);
    }
  });

  // ── Initialize (catches Puppeteer errors) ───────────────────────────────
  client.initialize().catch((err) => {
    const msg = err?.message || String(err);

    // "Execution context destroyed" is a known whatsapp-web.js navigation glitch
    // that happens right after WhatsApp Web authenticates. It's safe to restart.
    if (msg.includes("Execution context was destroyed") || msg.includes("navigation")) {
      console.log(`[${instanceName}] Navigation error after auth (expected) — restarting in 3s...`);
      session.status = "RECONNECTING";
      if (session.restarts < 10) {
        session.restarts++;
        setTimeout(() => createClient(instanceName, session), 3000);
      } else {
        console.error(`[${instanceName}] Init error: ${msg}`);
        session.status = "ERROR";
      }
    }
  });
  })();

  return session;
}

// ─── Global unhandled rejection / exception handlers ─────────────────────────
// Prevent any single session crash from taking down the whole server.
process.on("uncaughtException", (err) => {
  const msg = err?.message || String(err);
  if (
    msg.includes("Execution context was destroyed") ||
    msg.includes("Target closed") ||
    msg.includes("Session closed") ||
    msg.includes("navigation")
  ) {
    console.warn(`[bridge] Ignoring known Puppeteer error: ${msg.substring(0, 120)}`);
    // Try to restart any session in ERROR/CONNECTING state
    for (const [name, sess] of Object.entries(sessions)) {
      if (["INITIALIZING", "AUTHENTICATED", "RECONNECTING", "ERROR"].includes(sess.status)) {
        console.log(`[bridge] Auto-restarting session: ${name}`);
        setTimeout(() => createClient(name, sess), 3000);
      }
    }
  } else {
    console.error("[bridge] Uncaught exception:", msg);
  }
});

process.on("unhandledRejection", (reason) => {
  const msg = String(reason?.message || reason);
  if (
    msg.includes("Execution context was destroyed") ||
    msg.includes("Target closed") ||
    msg.includes("navigation")
  ) {
    console.warn(`[bridge] Ignoring known async Puppeteer error: ${msg.substring(0, 120)}`);
  } else {
    console.error("[bridge] Unhandled rejection:", msg);
  }
});

// ─── REST API Routes ──────────────────────────────────────────────────────────

app.get("/health", (req, res) => {
  res.json({
    status: "ok",
    service: "whatsapp-bridge",
    sessions: Object.keys(sessions).length,
    uptime: Math.round(process.uptime()),
  });
});

app.get("/sessions", (req, res) => {
  const result = Object.values(sessions).map((s) => ({
    name: s.name,
    status: s.status,
    phone: s.phone,
    has_qr: !!s.qr_base64,
    restarts: s.restarts,
    createdAt: s.createdAt,
  }));
  res.json(result);
});

// Create or get a session
app.post("/sessions/:name", (req, res) => {
  const { name } = req.params;
  if (sessions[name]) {
    const s = sessions[name];
    return res.json({ name: s.name, status: s.status, has_qr: !!s.qr_base64 });
  }
  console.log(`[bridge] Creating new session: ${name}`);
  const session = createClient(name);
  sessions[name] = session;
  res.status(201).json({
    name: session.name,
    status: session.status,
    has_qr: false,
    message: "Session initializing — poll /sessions/:name/qr in 8-12 seconds",
  });
});

// Force restart a session & regenerate QR
app.post("/sessions/:name/restart", async (req, res) => {
  const { name } = req.params;
  console.log(`[bridge] 🔄 Force restarting session: ${name}`);
  const existing = sessions[name];
  const session = createClient(name, existing);
  sessions[name] = session;
  res.json({
    name: session.name,
    status: session.status,
    message: "Session restarting — fresh QR will appear in 6-8 seconds",
  });
});

// Get QR code (poll until status = QR_READY)
app.get("/sessions/:name/qr", (req, res) => {
  const { name } = req.params;
  let session = sessions[name];

  if (!session) {
    console.log(`[bridge] ⚡ Session '${name}' requested but not found — auto-creating...`);
    session = createClient(name);
    sessions[name] = session;
  }

  if (session.status === "CONNECTED") {
    return res.json({ status: "CONNECTED", qr_code: null, phone: session.phone });
  }

  if (!session.qr_base64) {
    return res.status(200).json({
      status: session.status || "INITIALIZING",
      qr_code: null,
      message:
        session.status === "RECONNECTING"
          ? "Reconnecting after auth… retry in 3s"
          : "QR not ready — WhatsApp engine is starting. Retry in 2-3s.",
    });
  }

  res.json({
    status: session.status,
    qr_code: session.qr_base64,
    qr_raw: session.qr_raw,
    name,
  });
});

// Get session status
app.get("/sessions/:name", (req, res) => {
  const { name } = req.params;
  const session = sessions[name];
  if (!session) return res.status(404).json({ error: "Session not found" });
  res.json({
    name: session.name,
    status: session.status,
    phone: session.phone,
    pushname: session.pushname || null,
    platform: session.platform || "WhatsApp Web",
    has_qr: !!session.qr_base64
  });
});

// ─── Messaging Helpers & Auto-Recovery ──────────────────────────────────────
let recoveryLock = null;

async function restartSession(instanceName) {
  if (recoveryLock) {
    return await recoveryLock;
  }

  recoveryLock = (async () => {
    try {
      console.log(`[${instanceName}] 🔄 Auto-recovering session due to stale/detached frame...`);
      const existing = sessions[instanceName];
      const session = await createClient(instanceName, existing);
      sessions[instanceName] = session;

      // Wait up to 18 seconds for ready/connected state
      const start = Date.now();
      while (Date.now() - start < 18000) {
        if (session.status === "CONNECTED" && session.client) {
          console.log(`[${instanceName}] ✅ Session auto-recovered successfully!`);
          break;
        }
        await new Promise((r) => setTimeout(r, 600));
      }
      return session;
    } catch (e) {
      console.error(`[${instanceName}] Auto-recovery notice:`, e.message);
      return sessions[instanceName];
    } finally {
      recoveryLock = null;
    }
  })();

  return await recoveryLock;
}

async function safeSendMessage(session, chatId, content, options) {
  try {
    return await session.client.sendMessage(chatId, content, options);
  } catch (err) {
    const errMsg = err?.message || String(err);
    if (
      errMsg.includes("detached Frame") ||
      errMsg.includes("Target closed") ||
      errMsg.includes("Session closed") ||
      errMsg.includes("Execution context was destroyed") ||
      errMsg.includes("Protocol error") ||
      errMsg.includes("Evaluation failed")
    ) {
      console.warn(`[${session.name}] ⚠️ Frame detached / communication failure (${errMsg}). Triggering auto-recovery...`);
      const recoveredSession = await restartSession(session.name);
      if (recoveredSession && recoveredSession.client && recoveredSession.status === "CONNECTED") {
        console.log(`[${session.name}] 🔁 Re-dispatching message after session recovery...`);
        await new Promise((r) => setTimeout(r, 1200));
        return await recoveredSession.client.sendMessage(chatId, content, options);
      }
    }
    throw err;
  }
}

async function resolveMedia(mediaUrl, filename) {
  if (mediaUrl.startsWith("data:")) {
    const [meta, b64] = mediaUrl.split(";base64,");
    const mimetype = meta.replace("data:", "");
    return new MessageMedia(mimetype, b64, filename || "attachment");
  }

  // Check if it's a local backend upload URL or path
  const uploadsDir = path.resolve(__dirname, "../backend/uploads");
  let localFilename = null;

  if (mediaUrl.includes("/uploads/")) {
    const parts = mediaUrl.split("/uploads/");
    localFilename = decodeURIComponent(parts[parts.length - 1]);
  }

  if (localFilename) {
    const localFilePath = path.join(uploadsDir, localFilename);
    if (fs.existsSync(localFilePath)) {
      console.log(`[bridge] 📁 Loading media directly from disk: ${localFilePath}`);
      return MessageMedia.fromFilePath(localFilePath);
    }
  }

  // Otherwise download via URL with proper URI encoding
  const cleanUrl = encodeURI(decodeURI(mediaUrl));
  return await MessageMedia.fromUrl(cleanUrl, { unsafeMime: true, filename: filename || "attachment" });
}

// ─── Messaging & Chat Sync Routes ───────────────────────────────────────────
// Send Text Message
app.post("/sessions/:name/messages/send-text", async (req, res) => {
  const { name } = req.params;
  const { number, text } = req.body;
  const session = sessions[name];
  if (!session || !session.client || session.status !== "CONNECTED") {
    return res.status(400).json({ error: `Session '${name}' is not connected to WhatsApp` });
  }
  try {
    let chatId = String(number).trim();
    if (!chatId.includes("@")) {
      const clean = chatId.replace(/\D/g, "");
      chatId = `${clean}@c.us`;
    }
    console.log(`[${name}] 📤 Sending text to ${chatId}: "${text?.substring(0, 40)}..."`);
    const sent = await safeSendMessage(session, chatId, text);
    console.log(`[${name}] ✅ Sent successfully! ID: ${sent?.id?.id}`);
    res.json({
      status: "SENT",
      id: sent?.id?.id || `WAMSG_${Date.now()}`,
      to: chatId,
      timestamp: Math.floor(Date.now() / 1000),
    });
  } catch (err) {
    console.error(`[${name}] ❌ Failed to send text:`, err.message);
    res.status(500).json({ error: err.message });
  }
});

// Send Media Message (Image / Document)
app.post("/sessions/:name/messages/send-media", async (req, res) => {
  const { name } = req.params;
  const { number, mediaUrl, caption, filename } = req.body;
  const session = sessions[name];
  if (!session || !session.client || session.status !== "CONNECTED") {
    return res.status(400).json({ error: `Session '${name}' is not connected to WhatsApp` });
  }
  try {
    let chatId = String(number).trim();
    if (!chatId.includes("@")) {
      const clean = chatId.replace(/\D/g, "");
      chatId = `${clean}@c.us`;
    }
    console.log(`[${name}] 📤 Sending media to ${chatId}: ${mediaUrl}`);
    const media = await resolveMedia(mediaUrl, filename);
    const sent = await safeSendMessage(session, chatId, media, { caption: caption || "" });
    console.log(`[${name}] ✅ Media sent successfully! ID: ${sent?.id?.id}`);
    res.json({
      status: "SENT",
      id: sent?.id?.id || `WAMSG_${Date.now()}`,
      to: chatId,
      timestamp: Math.floor(Date.now() / 1000),
    });
  } catch (err) {
    console.error(`[${name}] ❌ Failed to send media:`, err.message);
    res.status(500).json({ error: err.message });
  }
});

// Get All WhatsApp Chats & Contacts
app.get("/sessions/:name/chats", async (req, res) => {
  const { name } = req.params;
  const session = sessions[name];
  if (!session || !session.client || session.status !== "CONNECTED") {
    return res.json([]);
  }
  try {
    const chats = await session.client.getChats();
    const result = chats.map((c) => ({
      id: c.id._serialized,
      name: c.name || c.formattedTitle || c.id.user || "Unknown",
      phone: c.id.user || "",
      isGroup: c.isGroup || false,
      unreadCount: c.unreadCount || 0,
      timestamp: c.timestamp || Math.floor(Date.now() / 1000),
      lastMessage: c.lastMessage
        ? {
            body: c.lastMessage.body || (c.lastMessage.hasMedia ? "[Media]" : ""),
            type: c.lastMessage.type,
            timestamp: c.lastMessage.timestamp,
            fromMe: c.lastMessage.fromMe,
          }
        : null,
    }));
    res.json(result);
  } catch (err) {
    console.error(`[${name}] ❌ Failed to fetch chats:`, err.message);
    res.json([]);
  }
});

// Get Messages for a specific WhatsApp Chat
app.get("/sessions/:name/chats/:chatId/messages", async (req, res) => {
  const { name, chatId } = req.params;
  const limit = parseInt(req.query.limit || "50", 10);
  const session = sessions[name];
  if (!session || !session.client || session.status !== "CONNECTED") {
    return res.json([]);
  }
  try {
    let target = decodeURIComponent(chatId);
    if (!target.includes("@")) {
      target = `${target.replace(/\D/g, "")}@c.us`;
    }
    const chat = await session.client.getChatById(target);
    const msgs = await chat.fetchMessages({ limit });
    const result = msgs.map((m) => ({
      id: m.id.id,
      from: m.from,
      to: m.to,
      fromMe: m.fromMe,
      body: m.body || "",
      type: m.type,
      timestamp: m.timestamp,
      hasMedia: m.hasMedia,
    }));
    res.json(result);
  } catch (err) {
    console.error(`[${name}] ❌ Failed to fetch messages for ${chatId}:`, err.message);
    res.json([]);
  }
});

// Disconnect / destroy session
app.delete("/sessions/:name", async (req, res) => {
  const { name } = req.params;
  const session = sessions[name];
  if (!session) return res.status(404).json({ error: "Session not found" });
  try { await session.client?.destroy(); } catch {}
  delete sessions[name];
  res.json({ status: "destroyed", name });
});

// ─── Start ────────────────────────────────────────────────────────────────────
app.listen(PORT, () => {
  console.log(`\n🚀 WhatsApp Bridge running on http://localhost:${PORT}`);
  console.log(`   POST /sessions/:name      — create session (real QR in ~10s)`);
  console.log(`   GET  /sessions/:name/qr   — get QR (poll every 3s)`);
  console.log(`   GET  /sessions/:name      — check connection status`);
  console.log(`   DEL  /sessions/:name      — disconnect & destroy`);
  console.log(`   GET  /health              — health check\n`);
});
