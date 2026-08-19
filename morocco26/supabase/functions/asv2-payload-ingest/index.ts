// RETIRED: the ASV2 payload registry is frozen and complete.
// This endpoint intentionally has no database client, no storage access and no secret.
Deno.serve((_req: Request) => new Response(JSON.stringify({error:'INGEST_RETIRED',status:'FROZEN_PAYLOAD_REGISTRY'}), {
  status: 410,
  headers: {'content-type':'application/json; charset=utf-8','cache-control':'no-store'}
}));
