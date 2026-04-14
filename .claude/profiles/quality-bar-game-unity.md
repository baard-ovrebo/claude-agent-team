# [QUALITY BAR — NON-NEGOTIABLE] — game-unity profile

Your code will be REJECTED if it does not meet these standards:

## PERFORMANCE FIRST — frame budget is 16.6ms (60 FPS) or 8.3ms (120 FPS)
- ZERO allocations per frame — no `new`, no `.ToArray()`, no LINQ in `Update`/`FixedUpdate`/`LateUpdate`
- Cache `GetComponent<T>()` results in `Awake`/`Start`, never call in Update
- Object pooling for anything spawned/despawned (bullets, enemies, VFX, UI popups)
- `string.Format` / string concatenation is a GC death trap in Update — use `StringBuilder` cached
- `foreach` on `List<T>` is fine; `foreach` on `IEnumerable<T>` often boxes — prefer `for`
- Never use `FindObjectOfType` / `GameObject.Find` in hot paths — cache the reference

## RESOURCE EFFICIENCY
- Respect the **8 GB RAM / integrated GPU** floor — this is the median gamer's machine
- Texture memory: atlas small sprites, compress, mipmap appropriately
- Mesh budgets: combine static meshes, use LOD, bake lighting where possible
- Audio: stream long clips, don't load a 30-minute OST into memory
- Coroutines: explicit `StopCoroutine` on teardown; prefer async/await with CancellationToken for new code

## CODE STRUCTURE
- Data-oriented: separate data (struct, ScriptableObject) from behavior (MonoBehaviour)
- Single responsibility per MonoBehaviour — a "PlayerController" doing movement + inventory + audio is a refactor waiting to happen
- ScriptableObjects for tunable data, not magic numbers in MonoBehaviour fields
- Event-driven decoupling — use C# `event`/`UnityEvent` instead of direct coupling
- Before writing ANY helper/utility, grep for an existing one (especially `Vector3` extensions)

## TOP 5 COUNTER-PATTERNS

### 1. GetComponent in Update
```csharp
// BAD — calls Unity's component lookup every frame
void Update() {
    GetComponent<Rigidbody>().velocity = dir;
}

// GOOD — cache in Awake
Rigidbody _rb;
void Awake() { _rb = GetComponent<Rigidbody>(); }
void Update() { _rb.velocity = dir; }
```

### 2. Allocating in Update (GC spikes = frame drops)
```csharp
// BAD — new array every frame, garbage pile
void Update() {
    var hits = Physics.OverlapSphere(transform.position, 5f); // allocates
    foreach (var h in hits) { /* ... */ }
}

// GOOD — non-alloc API with reusable buffer
readonly Collider[] _buffer = new Collider[32];
void Update() {
    int n = Physics.OverlapSphereNonAlloc(transform.position, 5f, _buffer);
    for (int i = 0; i < n; i++) { /* use _buffer[i] */ }
}
```

### 3. Instantiate/Destroy in Update (allocates, triggers GC)
```csharp
// BAD — allocates a bullet prefab every shot
void Fire() {
    var bullet = Instantiate(bulletPrefab, muzzle.position, muzzle.rotation);
    Destroy(bullet, 2f); // GC work
}

// GOOD — object pool
ObjectPool<Bullet> _pool;
void Fire() {
    var bullet = _pool.Get();
    bullet.transform.SetPositionAndRotation(muzzle.position, muzzle.rotation);
    bullet.TimeAlive = 0f;
}
```

### 4. String concat in Update
```csharp
// BAD — allocates new string every frame
void Update() {
    scoreText.text = "Score: " + score + " (combo: " + combo + ")";
}

// GOOD — only update when value changes
int _lastScore = -1, _lastCombo = -1;
readonly StringBuilder _sb = new StringBuilder(32);
void Update() {
    if (score == _lastScore && combo == _lastCombo) return;
    _sb.Clear().Append("Score: ").Append(score).Append(" (combo: ").Append(combo).Append(')');
    scoreText.text = _sb.ToString();
    _lastScore = score; _lastCombo = combo;
}
```

### 5. LINQ in Update
```csharp
// BAD — allocates enumerators, delegates, possibly arrays
void Update() {
    var visible = enemies.Where(e => e.IsVisible).ToList();
    foreach (var e in visible) e.UpdateAI();
}

// GOOD — plain for loop, no allocation
void Update() {
    for (int i = 0; i < enemies.Count; i++) {
        if (!enemies[i].IsVisible) continue;
        enemies[i].UpdateAI();
    }
}
```

## OTHER PATTERNS
- Debug.Log in Update → guard behind `#if UNITY_EDITOR`
- Camera.main in hot paths → cache the Camera reference
- Querying scene/hierarchy each frame → cache references in Awake
- Loading scenes synchronously → `SceneManager.LoadSceneAsync`
- `Resources.Load` at runtime → Addressables

## QUALITY AUDIT — machine-checkable

```yaml
cached_components: []            # MonoBehaviour fields holding cached GetComponent results
object_pools: []                 # pool names for Instantiate/Destroy replacement
nonalloc_physics_uses: []        # OverlapSphereNonAlloc, RaycastNonAlloc, etc.
string_builders_cached: []       # cached StringBuilders used in Update
update_allocations_avoided: []   # patterns you rejected that would have allocated
cleanup_on_destroy:              # what's released in OnDestroy/OnDisable
  - { type: "", where: "" }
coroutines_managed: []           # coroutines with explicit Stop on teardown
frame_budget_estimate_ms: ""     # estimated per-frame cost of your code
memory_mb_estimate: ""           # runtime memory footprint
shortcuts_rejected: []
```

Target: stay under 2ms per frame for game logic so rendering has budget.
