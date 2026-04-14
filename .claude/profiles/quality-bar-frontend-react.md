# [QUALITY BAR — NON-NEGOTIABLE] — frontend-react profile

Your code will be REJECTED if it does not meet these standards:

## PERFORMANCE FIRST
- Zero allocations in render paths (components, map callbacks, event handlers)
- Proper data structures (Set/Map for O(1) lookups, not linear scans with find/includes)
- Batched state updates (no setState in a for/forEach loop — functional updates inside .map() are fine)
- Early returns and lazy evaluation — don't do work the caller doesn't need
- No synchronous I/O in render paths
- No unnecessary re-computation of values that don't change (useMemo for derived data)

## RESOURCE EFFICIENCY
- Must run well on 8 GB RAM / integrated GPU / slow disk / 3G network
- All resources cleaned up (listeners, timers, subscriptions, AbortControllers)
- No unbounded caches or buffers — evict or cap everything
- GPU awareness — minimize re-renders, avoid layout thrashing, batch DOM ops

## CODE STRUCTURE
- Single responsibility per component / hook / function
- No duplicated logic — if the same pattern appears 3+ times, extract a utility
- Before writing ANY helper/utility/type, grep the project for an existing one
- Shared types/interfaces/models live in ONE place — import, don't redefine
- Error handling at boundaries (API edges, user input, external calls)
- No dead code, no commented-out blocks

## TOP 5 COUNTER-PATTERNS (study before writing)

### 1. Inline `style={{...}}` in JSX → breaks React.memo, allocates every render
```tsx
// BAD
<div style={{padding: 8, color: 'red'}}>{label}</div>

// GOOD
const LABEL_STYLE = { padding: 8, color: 'red' };
<div style={LABEL_STYLE}>{label}</div>
```

### 2. Inline arrow functions in JSX props → breaks React.memo
```tsx
// BAD
<TaskRow onToggle={() => toggle(task.id)} />

// GOOD
const handleToggle = useCallback((id: string) => toggle(id), [toggle]);
<TaskRow onToggle={handleToggle} id={task.id} />
```

### 3. `array.find` / `array.includes` in a render or loop → O(n·m) scaling trap
```tsx
// BAD
{tasks.map(t => <Row assignee={users.find(u => u.id === t.assigneeId)?.name} />)}

// GOOD
const userName = useMemo(() => new Map(users.map(u => [u.id, u.name])), [users]);
{tasks.map(t => <Row assignee={userName.get(t.assigneeId)} />)}
```

### 4. Missing React.memo on list-row components
```tsx
// BAD — all rows re-render on any change
function TaskRow({task, onToggle}) { return <div>...</div>; }

// GOOD — only rows with changed props re-render
const TaskRow = React.memo(function TaskRow({task, onToggle}) {
  return <div>...</div>;
});
```

### 5. Deep clone via JSON.parse(JSON.stringify(...))
```ts
// BAD
const copy = JSON.parse(JSON.stringify(obj));

// GOOD
const copy = structuredClone(obj);
setTasks(prev => prev.map(t => t.id === id ? {...t, status: 'done'} : t));
```

## OTHER PATTERNS
- Rebuilding entire lists when one item changed → update one with referential stability
- setState/update inside for/forEach/while → collect into array, call setState once
- Loading all data then filtering in memory → filter server-side via query string
- Fetching cached data → reuse the shared API client's cache
- 3-layer validation → validate at the boundary once

## QUALITY AUDIT — machine-checkable (emit this YAML block at the end)

```yaml
# Every claim here is cross-checked against the code.
memoized_components: []       # [TaskRow, StatusBadge, ...]
usecallback_handlers: []      # handler names wrapped in useCallback
usememo_derivations: []       # values wrapped in useMemo
hoisted_style_constants: []   # module-scope style object names
set_uses:
  - { name: "", purpose: "" }
map_uses:
  - { name: "", purpose: "" }
cleanup_registered:
  - { type: "", where: "" }
batched_operations: []
shortcuts_rejected: []
memory_at_10x: ""
memory_at_100x: ""
```

If this section is missing or fabricated, your work is INCOMPLETE.
