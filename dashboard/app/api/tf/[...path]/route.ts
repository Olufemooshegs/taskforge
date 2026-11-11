import { NextRequest, NextResponse } from 'next/server';

const INTERNAL_API = process.env.INTERNAL_API_URL || 'http://backend:8000/api/v1';
const API_KEY = process.env.API_KEY || 'dev-api-key-change-me';

async function handler(req: NextRequest, ctx: { params: { path: string[] } }) {
  const target = `${INTERNAL_API}/${ctx.params.path.join('/')}${req.nextUrl.search}`;
  const init: RequestInit = {
    method: req.method,
    headers: { 'X-API-Key': API_KEY, 'Content-Type': 'application/json' },
    cache: 'no-store',
  };
  if (req.method !== 'GET' && req.method !== 'HEAD') {
    init.body = await req.text();
  }
  const resp = await fetch(target, init);
  const body = await resp.text();
  return new NextResponse(body, {
    status: resp.status,
    headers: { 'Content-Type': resp.headers.get('content-type') || 'application/json' },
  });
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
