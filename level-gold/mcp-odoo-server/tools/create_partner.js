/**
 * create_partner — HITL-gated customer/vendor creation in Odoo.
 *
 * Requires an approval file in AI_Employee_Vault/Approved/ before creating.
 *
 * Required params:
 *   - name:          Partner full name
 *   - approval_file: Filename in Approved/ (e.g. APPROVAL_partner_abc123.md)
 *
 * Optional params:
 *   - email:         Contact email
 *   - phone:         Contact phone
 *   - is_company:    true for company, false for individual (default: true)
 *   - customer_rank: 1 to mark as customer (default: 1)
 *   - supplier_rank: 1 to mark as vendor (default: 0)
 */

import { existsSync } from "fs";
import { join } from "path";
import { odooCall } from "./odoo_auth.js";

const VAULT_PATH = process.env.VAULT_PATH || "AI_Employee_Vault";

export async function createPartner({
  name,
  approval_file,
  email = "",
  phone = "",
  is_company = true,
  customer_rank = 1,
  supplier_rank = 0,
}) {
  // --- HITL gate ---
  const approvalPath = join(VAULT_PATH, "Approved", approval_file);
  if (!existsSync(approvalPath)) {
    throw new Error(
      `HITL gate: approval file not found at ${approvalPath}. ` +
        `Move the approval file to /Approved/ first.`
    );
  }

  // Check if partner already exists (dedup by email)
  if (email) {
    const existing = await odooCall("res.partner", "search_read", {
      domain: [["email", "=", email]],
      fields: ["id", "name", "email"],
      limit: 1,
    });
    if (existing.length > 0) {
      return {
        partner_id: existing[0].id,
        name: existing[0].name,
        email: existing[0].email,
        created: false,
        message: `Partner already exists with email ${email}`,
      };
    }
  }

  const partnerData = {
    name,
    is_company,
    customer_rank,
    supplier_rank,
    ...(email && { email }),
    ...(phone && { phone }),
  };

  const createResult = await odooCall("res.partner", "create", {
    vals_list: [partnerData],
  });

  // Odoo REST API returns [id] (list) for create with vals_list — normalise to integer.
  const partnerId = Array.isArray(createResult) ? createResult[0] : createResult;

  return {
    partner_id: partnerId,
    name,
    email,
    created: true,
  };
}
