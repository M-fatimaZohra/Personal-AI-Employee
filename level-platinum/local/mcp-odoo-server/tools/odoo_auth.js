/**
 * Odoo JSON-RPC 2.0 client using API key bearer token authentication.
 * Odoo 19+ endpoint: POST /json/2/{model}/{method}
 *
 * Required env vars:
 *   ODOO_URL     — e.g. http://localhost:8069
 *   ODOO_DB      — e.g. fte_business
 *   ODOO_API_KEY — generated from Settings → Users → Administrator → API Keys
 */

const ODOO_URL = process.env.ODOO_URL || "http://localhost:8069";
const ODOO_DB = process.env.ODOO_DB || "fte_business";
const ODOO_API_KEY = process.env.ODOO_API_KEY || "";

if (!ODOO_API_KEY) {
  console.error("[mcp-odoo] WARNING: ODOO_API_KEY not set — all requests will fail.");
}

/**
 * Call any Odoo model method via JSON-RPC 2.0.
 *
 * @param {string} model  - Odoo model name, e.g. "account.move"
 * @param {string} method - Method name, e.g. "search_read"
 * @param {object} params - Method parameters (domain, fields, context, etc.)
 * @returns {Promise<any>} - Parsed result from Odoo
 * @throws {Error} on HTTP error or Odoo JSON-RPC error
 */
// Methods that accept a context parameter alongside their data params.
// Write operations (create, write, action_post) must NOT receive context
// at the top level — Odoo 17+ REST API /json/2/ treats every top-level key
// as a positional parameter, and an unexpected "context" key causes
// "unhashable type: list" errors in the ORM dispatcher.
const _CONTEXT_SAFE_METHODS = new Set([
  "search", "search_read", "read", "fields_get", "name_search",
]);

export async function odooCall(model, method, params = {}) {
  const url = `${ODOO_URL}/json/2/${model}/${method}`;

  // Only inject context for read-only methods that explicitly support it.
  const body = _CONTEXT_SAFE_METHODS.has(method)
    ? { ...params, context: { lang: "en_US", ...(params.context || {}) } }
    : { ...params };

  const response = await fetch(url, {
    method: "POST",
    headers: {
      Authorization: `bearer ${ODOO_API_KEY}`,
      "X-Odoo-Database": ODOO_DB,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`Odoo HTTP ${response.status}: ${body.slice(0, 200)}`);
  }

  const data = await response.json();

  // Odoo JSON-RPC error format: { error: { code, message, data } }
  if (data && data.error) {
    const err = data.error;
    throw new Error(`Odoo RPC error ${err.code}: ${err.message} — ${err.data?.message || ""}`);
  }

  return data;
}

/**
 * Validate Odoo connection. Returns true if reachable, false otherwise.
 */
export async function validateConnection() {
  try {
    await odooCall("res.partner", "search", { domain: [], limit: 1 });
    return true;
  } catch {
    return false;
  }
}

export { ODOO_URL, ODOO_DB };
