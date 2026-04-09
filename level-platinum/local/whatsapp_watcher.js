// whatsapp_watcher.js — WhatsApp Watcher for Silver FTE (Baileys ESM rewrite)
//
// Responsibility 1 — RECEIVE:
//   sock.ev.on('messages.upsert') → keyword filter → write WHATSAPP_*.md to /Needs_Action/
//
// Responsibility 2 — SEND:
//   chokidar watches /Approved/ for APPROVAL_WA_*.md
//   → normalize JID → 2s composing presence → sendMessage → move to /Archive/
//
// Usage:
//   node whatsapp_watcher.js           # normal run (PM2 managed)
//   node whatsapp_watcher.js --setup   # first-time QR scan — exits after session saved

import makeWASocket, {
    useMultiFileAuthState,
    DisconnectReason,
    fetchLatestBaileysVersion,
} from '@whiskeysockets/baileys';
import pino           from 'pino';
import chokidar       from 'chokidar';
import fs             from 'fs';
import path           from 'path';
import { fileURLToPath } from 'url';
import dotenv         from 'dotenv';
import qrcode         from 'qrcode-terminal';

// ─── ESM __dirname shim ────────────────────────────────────────────────────────
const __filename = fileURLToPath(import.meta.url);
const __dirname  = path.dirname(__filename);

dotenv.config({ path: path.join(__dirname, '.env') });

// ─── Configuration ─────────────────────────────────────────────────────────────
const VAULT_PATH   = process.env.VAULT_PATH || 'AI_Employee_Vault';
const NEEDS_ACTION = path.join(VAULT_PATH, 'Needs_Action');
const APPROVED_DIR = path.join(VAULT_PATH, 'Approved');
const ARCHIVE_DIR  = path.join(VAULT_PATH, 'Archive');
const LOGS_DIR     = path.join(VAULT_PATH, 'Logs');
const SESSION_DIR  = path.join(__dirname, '..', '.secrets', 'whatsapp_session');
const STATE_DIR    = '.state';
const STATE_FILE   = path.join(STATE_DIR, 'wa_processed_ids.json');

const DRY_RUN  = process.env.DRY_RUN === 'true';
const IS_SETUP = process.argv.includes('--setup');

const RAW_KEYWORDS = process.env.WA_URGENT_KEYWORDS || 'urgent,asap,invoice,payment,help,emergency,critical';
const KEYWORDS = RAW_KEYWORDS.split(',').map(k => k.trim().toLowerCase()).filter(Boolean);

// ─── Global socket ref (needed for graceful shutdown across reconnects) ─────────
let sock = null;

// ─── Approval watcher guard — start only once, even across reconnects ───────────
let approvalWatcherStarted = false;

// ─── Deduplication ─────────────────────────────────────────────────────────────
function loadProcessedIds() {
    try {
        if (!fs.existsSync(STATE_DIR)) fs.mkdirSync(STATE_DIR, { recursive: true });
        if (!fs.existsSync(STATE_FILE)) return new Set();
        return new Set(JSON.parse(fs.readFileSync(STATE_FILE, 'utf8')));
    } catch {
        return new Set();
    }
}

function saveProcessedIds(ids) {
    try {
        if (!fs.existsSync(STATE_DIR)) fs.mkdirSync(STATE_DIR, { recursive: true });
        fs.writeFileSync(STATE_FILE, JSON.stringify([...ids], null, 2), 'utf8');
    } catch (e) {
        console.error('[WA] Dedup save failed:', e.message);
    }
}

let processedIds = loadProcessedIds();

// ─── Structured logging (JSON Lines, matches Silver FTE audit format) ───────────
function logAction(result, action, details = {}) {
    const today   = new Date().toISOString().slice(0, 10);
    const logFile = path.join(LOGS_DIR, `${today}.json`);
    const entry   = JSON.stringify({
        timestamp: new Date().toISOString(),
        action,
        actor: 'whatsapp_watcher',
        result,
        ...details,
    });
    try {
        if (!fs.existsSync(LOGS_DIR)) fs.mkdirSync(LOGS_DIR, { recursive: true });
        fs.appendFileSync(logFile, entry + '\n', 'utf8');
    } catch (e) {
        console.error('[WA] Log write failed:', e.message);
    }
}

// ─── YAML frontmatter parser (no external dep) ─────────────────────────────────
function parseYamlFrontmatter(content) {
    const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---/);
    if (!match) return {};
    const yaml = {};
    for (const line of match[1].split(/\r?\n/)) {
        const colonIdx = line.indexOf(':');
        if (colonIdx === -1) continue;
        const key = line.slice(0, colonIdx).trim();
        const val = line.slice(colonIdx + 1).trim().replace(/^["']|["']$/g, '');
        if (key) yaml[key] = val;
    }
    return yaml;
}

// Extracts text under ## Section heading (until next ## or EOF)
function extractSection(content, sectionTitle) {
    const regex = new RegExp(`## ${sectionTitle}\\r?\\n([\\s\\S]*?)(?=\\r?\\n## |$)`);
    const match = content.match(regex);
    return match ? match[1].trim() : '';
}

// ─── JID normalization ─────────────────────────────────────────────────────────
// Baileys uses @s.whatsapp.net for individual contacts.
// Old whatsapp-web.js used @c.us — normalize any legacy values in saved files.
function normalizeJid(jid) {
    if (!jid) return null;
    if (jid.endsWith('@c.us')) return jid.replace('@c.us', '@s.whatsapp.net');
    return jid;
}

// ─── Part 1: RECEIVE — messages.upsert → WHATSAPP_*.md ─────────────────────────
async function handleIncomingMessage(msg) {
    const jid = msg.key.remoteJid;

    // Skip groups, broadcasts, and self-sent messages
    if (!jid || jid.endsWith('@g.us') || jid === 'status@broadcast') return;
    if (msg.key.fromMe) return;

    // Extract message text (handles plain text + quoted/extended messages)
    const text =
        msg.message?.conversation ||
        msg.message?.extendedTextMessage?.text ||
        msg.message?.imageMessage?.caption ||
        msg.message?.videoMessage?.caption ||
        '';

    // Skip empty messages (stickers, reactions, unsupported media with no caption)
    if (!text.trim()) return;

    // Dedup by Baileys message key ID
    const msgId = msg.key.id;
    if (processedIds.has(msgId)) return;
    processedIds.add(msgId);
    saveProcessedIds(processedIds);

    // Keyword detection — used for priority tagging only, NOT as a gate
    // Work-relatedness is determined by Claude via the fte-whatsapp-reply skill
    const body           = text.toLowerCase();
    const matchedKeywords = KEYWORDS.filter(k => body.includes(k));

    // Prefer pushName (what the contact set as their display name)
    const chatName = msg.pushName || jid.split('@')[0];
    const priority = matchedKeywords.some(k =>
        ['urgent', 'emergency', 'critical', 'asap', 'sos'].includes(k)
    ) ? 'high' : 'normal';

    const now       = new Date().toISOString();
    const safeId    = jid.replace(/[^a-zA-Z0-9]/g, '_');
    const dateStamp = now.slice(0, 10).replace(/-/g, '');
    const timeStamp = now.slice(11, 16).replace(':', ''); // HHMM — unique per message
    const filename  = `WHATSAPP_${safeId}_${dateStamp}_${timeStamp}.md`;
    const filepath  = path.join(NEEDS_ACTION, filename);

    const fileContent = [
        '---',
        `type: whatsapp_message`,
        `chat_id: "${jid}"`,
        `chat_name: "${chatName}"`,
        `message_id: "${msgId}"`,
        `date: "${now}"`,
        `status: needs_action`,
        `priority: ${priority}`,
        `keywords_matched: [${matchedKeywords.map(k => `"${k}"`).join(', ')}]`,
        `source: WhatsApp`,
        `processed_by: null`,
        '---',
        '',
        text,
    ].join('\n');

    if (DRY_RUN) {
        console.log(`[WA] DRY_RUN — would create: ${filename}`);
        logAction('dry_run', 'message_received', { file: filename, chat_id: jid, keywords: matchedKeywords });
        return;
    }

    try {
        if (!fs.existsSync(NEEDS_ACTION)) fs.mkdirSync(NEEDS_ACTION, { recursive: true });
        fs.writeFileSync(filepath, fileContent, 'utf8');
        console.log(`[WA] Created: ${filename}  (keywords: ${matchedKeywords.join(', ')})`);
        logAction('success', 'message_received', {
            file: filename, chat_id: jid, chat_name: chatName,
            keywords: matchedKeywords, priority,
        });
    } catch (e) {
        console.error(`[WA] Failed to write ${filename}:`, e.message);
        logAction('error', 'message_write_failed', { file: filename, error: e.message });
    }
}

// ─── Part 2: SEND — chokidar /Approved/ + sendMessage ──────────────────────────
function startApprovalWatcher() {
    if (approvalWatcherStarted) return;
    approvalWatcherStarted = true;

    [APPROVED_DIR, ARCHIVE_DIR].forEach(d => {
        if (!fs.existsSync(d)) fs.mkdirSync(d, { recursive: true });
    });

    chokidar.watch(path.join(APPROVED_DIR, 'APPROVAL_WA_*.md'), {
        persistent:       true,
        ignoreInitial:    false,
        awaitWriteFinish: { stabilityThreshold: 500, pollInterval: 100 },
    }).on('add', filePath => handleApproval(filePath));

    console.log('[WA] Approval watcher active — monitoring /Approved/ for APPROVAL_WA_*.md');
}

async function handleApproval(filePath) {
    const filename = path.basename(filePath);
    try {
        const content     = fs.readFileSync(filePath, 'utf8');
        const frontmatter = parseYamlFrontmatter(content);
        const rawJid      = frontmatter.chat_id;
        const jid         = normalizeJid(rawJid);

        if (!jid) {
            console.error(`[WA] Missing or invalid chat_id in ${filename} — skipping`);
            logAction('error', 'approval_missing_jid', { file: filename });
            return;
        }

        // Accept @s.whatsapp.net (standard) and @lid (WhatsApp linked-device privacy format)
        const validJid = jid.endsWith('@s.whatsapp.net') || jid.endsWith('@lid');
        if (!validJid) {
            console.error(`[WA] JID "${jid}" is not a valid send target — skipping`);
            logAction('error', 'approval_bad_jid', { file: filename, jid });
            return;
        }

        const replyText = extractSection(content, 'Proposed Reply');
        if (!replyText) {
            console.error(`[WA] No "## Proposed Reply" section in ${filename} — skipping`);
            logAction('error', 'approval_no_reply_text', { file: filename });
            return;
        }

        if (DRY_RUN) {
            console.log(`[WA] DRY_RUN — would send to ${jid}: "${replyText.slice(0, 60)}..."`);
            logAction('dry_run', 'reply_send', { file: filename, jid });
            moveToArchive(filePath, filename, 'dry_run');
            return;
        }

        // Stealth: send composing presence for 2 seconds before message
        await sock.sendPresenceUpdate('composing', jid);
        await new Promise(r => setTimeout(r, 2000));
        await sock.sendPresenceUpdate('paused', jid);

        await sock.sendMessage(jid, { text: replyText });
        console.log(`[WA] Sent reply → ${jid}  (source: ${filename})`);
        logAction('success', 'reply_sent', {
            file: filename, jid,
            preview: replyText.slice(0, 80),
        });
        moveToArchive(filePath, filename, 'sent');

    } catch (e) {
        console.error(`[WA] Approval handling failed for ${filename}:`, e.message);
        logAction('error', 'approval_failed', { file: filename, error: e.message });
    }
}

function moveToArchive(src, filename, status) {
    try {
        if (!fs.existsSync(ARCHIVE_DIR)) fs.mkdirSync(ARCHIVE_DIR, { recursive: true });
        const content = fs.readFileSync(src, 'utf8');
        const updated = content.replace(/^status: .+$/m, `status: ${status}`);
        fs.writeFileSync(path.join(ARCHIVE_DIR, filename), updated, 'utf8');
        fs.unlinkSync(src);
    } catch (e) {
        console.error(`[WA] Failed to archive ${filename}:`, e.message);
    }
}

// ─── Core: connectToWhatsApp (called on boot + on non-logout reconnects) ────────
async function connectToWhatsApp() {
    const { state, saveCreds } = await useMultiFileAuthState(SESSION_DIR);
    const { version }          = await fetchLatestBaileysVersion();

    sock = makeWASocket({
        version,
        auth:   state,
        logger: pino({ level: 'silent' }), // suppress Baileys internal noise
    });

    // Persist credentials whenever they update (after QR scan + on key rotation)
    sock.ev.on('creds.update', saveCreds);

    // Connection lifecycle
    sock.ev.on('connection.update', async (update) => {
        const { connection, lastDisconnect, qr } = update;

        // QR code — render in terminal for first-time setup
        if (qr) {
            console.log('\n[WA] Scan this QR code with WhatsApp mobile (Settings → Linked Devices):\n');
            qrcode.generate(qr, { small: true });
            if (IS_SETUP) console.log('[WA] Waiting for scan — process will exit automatically after success.\n');
        }

        if (connection === 'close') {
            const code          = lastDisconnect?.error?.output?.statusCode ?? 500;
            const shouldReconnect = code !== DisconnectReason.loggedOut;

            console.log(`[WA] Connection closed (code=${code}) — reconnect=${shouldReconnect}`);
            logAction('warning', 'connection_closed', { code, reconnect: shouldReconnect });

            if (shouldReconnect) {
                await connectToWhatsApp();
            } else {
                console.log('[WA] Logged out. Delete .secrets/whatsapp_session/ and re-scan QR.');
                logAction('error', 'logged_out', {});
                process.exit(1);
            }
        }

        if (connection === 'open') {
            console.log(`[WA] Connected. Keywords: [${KEYWORDS.join(', ')}]  DRY_RUN=${DRY_RUN}`);
            logAction('success', 'client_ready', { keywords: KEYWORDS, dry_run: DRY_RUN });

            if (IS_SETUP) {
                console.log('[WA] --setup complete. Session saved to .secrets/whatsapp_session/');
                console.log('[WA] Run without --setup for normal operation.');
                await sock.end();
                process.exit(0);
            } else {
                startApprovalWatcher();
            }
        }
    });

    // Incoming messages
    sock.ev.on('messages.upsert', async ({ messages, type }) => {
        if (type !== 'notify') return; // 'notify' = new real-time messages only
        for (const msg of messages) {
            await handleIncomingMessage(msg);
        }
    });
}

// ─── Graceful shutdown (PM2 SIGINT/SIGTERM — prevents session corruption) ────────
async function gracefulShutdown(signal) {
    console.log(`\n[WA] ${signal} received — shutting down gracefully...`);
    logAction('info', 'shutdown_initiated', { signal });
    try {
        if (sock) await sock.end();
        console.log('[WA] Socket closed cleanly. Goodbye.');
    } catch (e) {
        console.error('[WA] Error during shutdown:', e.message);
    }
    process.exit(0);
}

process.on('SIGINT',  () => gracefulShutdown('SIGINT'));
process.on('SIGTERM', () => gracefulShutdown('SIGTERM'));

// ─── Boot ──────────────────────────────────────────────────────────────────────
console.log(`[WA] Starting WhatsApp watcher  (setup=${IS_SETUP}, DRY_RUN=${DRY_RUN})`);
console.log(`[WA] Keywords: ${KEYWORDS.join(', ')}`);
console.log(`[WA] Session: ${SESSION_DIR}`);
connectToWhatsApp();
