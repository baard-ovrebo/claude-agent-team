# [QUALITY BAR — NON-NEGOTIABLE] — backend-node profile

Your code will be REJECTED if it does not meet these standards:

## PERFORMANCE FIRST
- No N+1 queries — batch in one SQL / one `WHERE IN (...)` / one `Promise.all`
- Proper data structures (Set/Map for O(1) lookups, not linear scans)
- No synchronous I/O in request handlers — never use `readFileSync`, `execSync`, etc. in hot paths
- Stream large responses (don't `.toArray()` an iterator of 100k rows)
- No unnecessary re-computation — cache per-request or per-process where safe
- Pagination on every list endpoint (no unbounded result sets)

## RESOURCE EFFICIENCY
- All resources cleaned up: DB connections returned to pool, file handles closed, streams piped (not concatenated into memory)
- Connection pool sized appropriately — never open a new connection per request
- No unbounded in-memory caches — use LRU or TTL eviction
- Background timers/intervals cleaned up on shutdown
- Request/response size bounded (`express.json({ limit: '...' })`)

## CODE STRUCTURE
- Single responsibility per handler/service/module
- Validate input at the boundary ONCE (Zod/Joi/express-validator), trust internally
- Error handling at boundaries — one `catch` at the route level, not scattered
- Before writing ANY helper/utility/type, grep the project for an existing one
- Shared types live in ONE place — import, don't redefine

## TOP 5 COUNTER-PATTERNS

### 1. N+1 queries (classic)
```ts
// BAD — 1 + N queries
const users = await db.query('SELECT * FROM users');
for (const u of users) u.posts = await db.query('SELECT * FROM posts WHERE user_id = ?', u.id);

// GOOD — 2 queries total, O(n) join
const users = await db.query('SELECT * FROM users');
const ids = users.map(u => u.id);
const posts = await db.query('SELECT * FROM posts WHERE user_id IN (?)', [ids]);
const byUser = new Map();
for (const p of posts) {
  if (!byUser.has(p.user_id)) byUser.set(p.user_id, []);
  byUser.get(p.user_id).push(p);
}
for (const u of users) u.posts = byUser.get(u.id) ?? [];
```

### 2. Synchronous I/O in request handlers
```ts
// BAD
app.get('/data', (_, res) => {
  const data = fs.readFileSync('data.json'); // blocks event loop
  res.json(JSON.parse(data));
});

// GOOD
app.get('/data', async (_, res) => {
  const data = await fs.promises.readFile('data.json');
  res.json(JSON.parse(data));
});
```

### 3. Loading all data then filtering in memory
```ts
// BAD
const all = await db.query('SELECT * FROM tasks');
const pending = all.filter(t => t.status === 'pending');

// GOOD
const pending = await db.query('SELECT * FROM tasks WHERE status = ?', ['pending']);
```

### 4. Opening new DB connections per request
```ts
// BAD
app.get('/users', async (_, res) => {
  const client = new PgClient(); // new socket every request
  await client.connect();
  const users = await client.query('SELECT * FROM users');
  client.end();
  res.json(users);
});

// GOOD — share a connection pool
const pool = new Pool({ max: 10 });
app.get('/users', async (_, res) => {
  const users = await pool.query('SELECT * FROM users');
  res.json(users.rows);
});
```

### 5. Unbounded in-memory caches
```ts
// BAD
const cache = new Map(); // grows forever
function get(key) { if (!cache.has(key)) cache.set(key, expensive(key)); return cache.get(key); }

// GOOD — LRU with cap
import { LRUCache } from 'lru-cache';
const cache = new LRUCache({ max: 1000, ttl: 5 * 60 * 1000 });
```

## OTHER PATTERNS
- No error handling on `await` → wrap in try/catch at the route
- Sending full objects when client needs 3 fields → select only what's used
- `JSON.parse(JSON.stringify(obj))` for cloning → `structuredClone`
- Synchronous CPU-heavy work in a handler → use a worker thread

## QUALITY AUDIT — machine-checkable

```yaml
endpoints_with_pagination: []     # routes that return lists — must all have ?limit= or similar
batched_queries: []               # places N+1 was avoided
input_validators: []              # validation layer names (Zod schemas, express-validator chains)
async_io_routes: []               # routes that read files/make HTTP calls — confirm async
error_boundaries: []              # route-level try/catch blocks
connection_reuse: []              # pools/clients reused across requests
bounded_caches:                   # all caches with eviction
  - { name: "", eviction: "" }
cleanup_on_shutdown:              # what's released on SIGTERM
  - { type: "", where: "" }
memory_at_10x: ""                 # estimated memory at 10x load
memory_at_100x: ""
shortcuts_rejected: []
```
