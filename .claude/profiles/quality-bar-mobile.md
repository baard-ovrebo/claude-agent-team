# [QUALITY BAR — NON-NEGOTIABLE] — mobile profile (React Native / Flutter / native)

Your code will be REJECTED if it does not meet these standards:

## PERFORMANCE FIRST
- 60 FPS target — anything that pushes the main thread > 16ms blocks scrolling and animation
- Images: resize server-side or use a caching library (FastImage/CachedNetworkImage). Never load 4000x4000px into a thumbnail.
- Lists: always virtualize. `FlatList` with `keyExtractor` + `getItemLayout`, `ListView.builder` with `itemCount`. Never render 1000 rows synchronously.
- No heavy computation on the JS thread (RN) / main isolate (Flutter). Use Worklets / background isolates for >5ms work.
- Navigation animations run on the UI thread — don't block with sync work during transitions
- Debounce text input, throttle scroll handlers

## RESOURCE EFFICIENCY — budget for low-end Android
- Target: 2 GB RAM, slow flash storage, ARMv7. If it works there, it works everywhere.
- No unbounded in-memory caches — mobile OS kills apps aggressively at >300MB
- Bitmap memory is the #1 cause of OOM — always decode at display size, not source size
- Battery: no wake-locks beyond what's necessary, no polling loops (use push or long-poll)
- Network: retry with backoff, coalesce requests, use HTTP caching headers, compress payloads
- Storage: SQLite/Room/CoreData — not JSON-on-disk for structured data

## CODE STRUCTURE
- Separate UI from business logic: ViewModel (MVVM) / Bloc / Redux / Zustand
- Platform-specific code in explicit boundaries (iOS vs Android, not inline `Platform.OS` checks scattered)
- Single responsibility per screen/component — no 2000-line "HomeScreen"
- Error handling at boundaries — one catch per async action, not try/catch everywhere
- Before writing ANY utility, grep for an existing one (date formatters, validators, etc.)

## TOP 5 COUNTER-PATTERNS

### 1. Unvirtualized lists
```tsx
// BAD — renders all 1000 rows synchronously, causes frame drops
<ScrollView>
  {tasks.map(t => <TaskRow task={t} />)}
</ScrollView>

// GOOD — virtualized, renders only visible rows
<FlatList
  data={tasks}
  keyExtractor={(t) => t.id}
  renderItem={({item}) => <TaskRow task={item} />}
  getItemLayout={(_, i) => ({length: 64, offset: 64 * i, index: i})}
/>
```

### 2. Loading full-resolution images
```tsx
// BAD — 4MB image decoded for a 100x100 thumbnail
<Image source={{ uri: photo.fullUrl }} style={{ width: 100, height: 100 }} />

// GOOD — request a server-sized thumbnail OR use a caching lib
<FastImage source={{ uri: photo.thumbnailUrl, priority: FastImage.priority.normal }} style={{ width: 100, height: 100 }} />
```

### 3. Heavy work on the JS/main thread
```tsx
// BAD — blocks UI during scroll
const onScroll = (e) => {
  const items = bigArray.map(transform).filter(predicate).sort(cmp); // O(n log n) per scroll event
  setVisibleItems(items);
};

// GOOD — precompute, use Animated with native driver, or move to Worklets
const sorted = useMemo(() => [...bigArray].sort(cmp), [bigArray]);
const onScroll = Animated.event([{ nativeEvent: { contentOffset: { y: scrollY } } }], { useNativeDriver: true });
```

### 4. Unbounded cache growing in memory
```ts
// BAD
const imageCache = new Map(); // grows forever
function getImage(url) { if (!imageCache.has(url)) imageCache.set(url, fetch(url)); return imageCache.get(url); }

// GOOD — LRU with size cap
import LRU from 'lru-cache';
const imageCache = new LRU({ max: 100, ttl: 60 * 60 * 1000 });
```

### 5. Polling battery drain
```ts
// BAD — wakes the radio every 5s
setInterval(async () => {
  const latest = await fetchLatest();
  setMessages(latest);
}, 5000);

// GOOD — push via WebSocket or long-poll, back off when app is backgrounded
useEffect(() => {
  const ws = new WebSocket(WS_URL);
  ws.onmessage = (e) => setMessages(JSON.parse(e.data));
  AppState.addEventListener('change', (state) => {
    if (state === 'background') ws.close();
  });
  return () => ws.close();
}, []);
```

## OTHER PATTERNS
- Inline arrow props on a virtualized list item → use `useCallback` (same as React)
- Re-render entire list on selection toggle → memo rows, stable handlers
- JSON parse of a huge blob on startup → lazy-load or use streaming parser
- Missing offline mode on mobile → every request should handle no-connection gracefully

## QUALITY AUDIT — machine-checkable

```yaml
virtualized_lists: []           # FlatList/SectionList/ListView.builder uses
image_size_respected: true/false  # server-side sizing or caching lib used
work_off_main_thread: []        # Worklets / isolates / native modules for heavy work
memoized_list_items: []
bounded_caches:
  - { name: "", eviction: "" }
battery_considerations: []      # push vs poll, foreground/background handling
offline_handling: []            # what happens without connectivity
memory_mb_estimate: ""
shortcuts_rejected: []
```

Target: maintain 60 FPS on low-end Android (2 GB RAM, ARMv7). If it stutters there, fix it.
