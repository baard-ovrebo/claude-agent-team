# [QUALITY BAR — NON-NEGOTIABLE] — backend-dotnet profile

Your code will be REJECTED if it does not meet these standards:

## PERFORMANCE FIRST
- No N+1 queries in EF Core — use `.Include()` / projection, never lazy-load in a loop
- `.AsNoTracking()` on read-only queries
- Proper data structures (`HashSet<T>`, `Dictionary<K,V>` for lookups, not repeated `List.Where`)
- `async`/`await` all the way down — never `.Result` or `.Wait()` in a request path
- Pagination on every list endpoint (`Skip`/`Take`, not `ToList` of everything)
- No `LINQ` materialization in hot loops — `.ToList()` inside a foreach is a trap

## RESOURCE EFFICIENCY
- `using`/`await using` on everything that implements `IDisposable`/`IAsyncDisposable`
- `HttpClient` reused (via `IHttpClientFactory`), never `new HttpClient()` per request
- `DbContext` scoped to the request — never shared across threads
- `MemoryCache` with `SlidingExpiration` / `AbsoluteExpiration`, never unbounded `Dictionary`
- `CancellationToken` threaded through async calls — honor client cancellation
- Large file transfers via `Stream`, not loaded fully into memory

## CODE STRUCTURE
- Single responsibility per controller / service / handler
- Input validation via `FluentValidation` or data annotations at the model binding layer
- Exception handling at middleware / filter level, not per-controller
- Before writing ANY helper/extension/DTO, grep for an existing one
- Shared types in ONE project (usually `*.Shared` or `*.Contracts`) — import, don't redefine

## TOP 5 COUNTER-PATTERNS

### 1. N+1 in EF Core (classic)
```csharp
// BAD — 1 + N queries
var users = await db.Users.ToListAsync();
foreach (var u in users) u.Posts = await db.Posts.Where(p => p.UserId == u.Id).ToListAsync();

// GOOD — single round trip
var users = await db.Users.Include(u => u.Posts).AsNoTracking().ToListAsync();
```

### 2. `.Result` / `.Wait()` in request paths (deadlock / thread starvation)
```csharp
// BAD
public IActionResult GetUser(int id) {
    var user = _userService.GetAsync(id).Result; // can deadlock, burns a thread
    return Ok(user);
}

// GOOD
public async Task<IActionResult> GetUser(int id, CancellationToken ct) {
    var user = await _userService.GetAsync(id, ct);
    return Ok(user);
}
```

### 3. New HttpClient per request (socket exhaustion)
```csharp
// BAD
public async Task<string> Fetch() {
    using var client = new HttpClient();
    return await client.GetStringAsync("https://api.example.com");
}

// GOOD — inject IHttpClientFactory
public class MyService(IHttpClientFactory factory) {
    public async Task<string> Fetch() {
        var client = factory.CreateClient("api");
        return await client.GetStringAsync("/endpoint");
    }
}
```

### 4. Linq in hot loops (repeated materialization)
```csharp
// BAD
foreach (var id in taskIds) {
    var user = users.Where(u => u.Id == id).FirstOrDefault(); // O(n) each iteration
    // ...
}

// GOOD
var byId = users.ToDictionary(u => u.Id); // O(n) once
foreach (var id in taskIds) {
    var user = byId.GetValueOrDefault(id); // O(1) each iteration
    // ...
}
```

### 5. Missing pagination
```csharp
// BAD
public async Task<List<Task>> GetAll() => await db.Tasks.ToListAsync(); // returns 1M rows

// GOOD
public async Task<List<Task>> GetAll(int page = 1, int size = 50) =>
    await db.Tasks.AsNoTracking().Skip((page - 1) * size).Take(size).ToListAsync();
```

## OTHER PATTERNS
- Long-running work in the request thread → `IHostedService` / `BackgroundService`
- Loading related entities eagerly everywhere → only when needed, projection often better
- `ToList()` before aggregation → use SQL aggregation (`Count`, `Sum`, `Average`)
- Manual JSON concatenation → use `System.Text.Json` with streaming

## QUALITY AUDIT — machine-checkable

```yaml
no_tracking_queries: []           # read-only queries marked AsNoTracking
eager_loads: []                   # Include() / projection chains
httpclient_factory_uses: []
async_through: []                 # methods that properly thread CancellationToken
disposables: []                   # using/await using blocks protecting resources
pagination_endpoints: []
dictionary_lookups: []            # places Dictionary/HashSet replaced List.Where
cancellation_propagated: true/false
memory_at_10x: ""
memory_at_100x: ""
shortcuts_rejected: []
```
