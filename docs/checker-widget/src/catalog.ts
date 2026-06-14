/**
 * Typed wrappers around the three JSON catalogs copied at build time from
 * packages/core/src/opencomplai_core/compliance_checker/data/.
 * Catalogs are inlined by esbuild — zero runtime fetches.
 */
import obligationsRaw from "./data/obligations.json";
import statusChangesRaw from "./data/status_changes.json";
import helpContentRaw from "./data/help_content.json";

export interface ObligationItem {
  id: string;
  title: string;
  body: string;
  article_ref: string;
}

export interface StatusChangeItem {
  id: string;
  title: string;
  body: string;
}

export interface HelpSection {
  title: string;
  body: string;
}

export interface EntityRole {
  title: string;
  description: string;
}

// Build typed maps from the raw JSON (keys become the id field)
const OBLIGATIONS: Record<string, Omit<ObligationItem, "id">> =
  obligationsRaw as Record<string, Omit<ObligationItem, "id">>;

const STATUS_CHANGES: Record<string, Omit<StatusChangeItem, "id">> =
  statusChangesRaw as Record<string, Omit<StatusChangeItem, "id">>;

export const HELP_CONTENT: Record<string, HelpSection> =
  helpContentRaw as Record<string, HelpSection>;

// Per-operator-role definitions, shared with the CLI wizard via help_content.json.
// Defensive default: older copies of the catalog may not carry the entity_roles key.
export const ENTITY_ROLES: Record<string, EntityRole> =
  ((helpContentRaw as Record<string, unknown>)["entity_roles"] as
    | Record<string, EntityRole>
    | undefined) ?? {};

export function getObligation(id: string): ObligationItem {
  const entry = OBLIGATIONS[id];
  if (!entry) throw new Error(`Unknown obligation id: ${id}`);
  return { id, ...entry };
}

export function getStatusChange(id: string): StatusChangeItem {
  const entry = STATUS_CHANGES[id];
  if (!entry) throw new Error(`Unknown status_change id: ${id}`);
  return { id, ...entry };
}
