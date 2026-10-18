import { createHmac, timingSafeEqual } from 'node:crypto';

/** Header format: `t=<unix seconds>,v1=<hex HMAC-SHA256 of "<t>.<raw body>">`. */
export const SIGNATURE_HEADER = 'X-Psp-Signature';

export type VerifyResult =
  | { ok: true; signedAt: number }
  | { ok: false; reason: 'missing_header' | 'malformed_header' | 'bad_signature' | 'stale' };

/**
 * Verifies a PSP webhook. The timestamp is part of the signed content, so a captured request cannot be
 * replayed with a fresh `t`; requests signed more than `toleranceSeconds` away from now are rejected.
 */
export function verifySignature(
  rawBody: Buffer,
  header: string | undefined,
  secret: string,
  nowMs: number,
  toleranceSeconds: number,
): VerifyResult {
  if (!header) return { ok: false, reason: 'missing_header' };

  const parts = new Map(header.split(',').map((part) => {
    const i = part.indexOf('=');
    return [part.slice(0, i).trim(), part.slice(i + 1).trim()] as const;
  }));
  const signedAt = Number(parts.get('t'));
  const given = parts.get('v1') ?? '';
  if (!Number.isInteger(signedAt) || !/^[0-9a-f]{64}$/.test(given)) {
    return { ok: false, reason: 'malformed_header' };
  }

  const expected = computeSignature(rawBody, secret, signedAt);
  if (!timingSafeEqual(Buffer.from(expected, 'hex'), Buffer.from(given, 'hex'))) {
    return { ok: false, reason: 'bad_signature' };
  }
  if (Math.abs(nowMs / 1000 - signedAt) > toleranceSeconds) {
    return { ok: false, reason: 'stale' };
  }
  return { ok: true, signedAt };
}

function computeSignature(rawBody: Buffer, secret: string, signedAt: number): string {
  return createHmac('sha256', secret).update(`${signedAt}.`).update(rawBody).digest('hex');
}

/** Builds a header value the way the PSP does. Used by tests and the local PSP simulator. */
export function signPayload(rawBody: Buffer, secret: string, signedAt: number): string {
  return `t=${signedAt},v1=${computeSignature(rawBody, secret, signedAt)}`;
}
