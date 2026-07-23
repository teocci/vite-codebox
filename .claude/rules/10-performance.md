# Performance

## Know the Cost

Every decision has a performance impact. Understand it before choosing.

## Array Methods Cost

| Method | Creates New Array | Can Break Early | Best For |
|--------|------------------|-----------------|----------|
| `for` | No | Yes | Performance-critical loops |
| `for...of` | No | Yes | Readable iteration |
| `forEach` | No | No | Side effects |
| `map` | Yes | No | Transformations |
| `filter` | Yes | No | Subsetting |
| `reduce` | No* | No | Aggregation |
| `find` | No | Yes | First match |
| `some` | No | Yes | Existence check |
| `every` | No | Yes | All match check |

```javascript
// Large dataset (10k+ items) - avoid chaining
// Bad - 3 iterations, 2 intermediate arrays
const result = items
  .filter(x => x.active)
  .map(x => x.id)
  .slice(0, 10)

// Good - single pass, early exit
const result = []
for (const item of items) {
  if (item.active) {
    result.push(item.id)
    if (result.length >= 10) break
  }
}
```

## DOM Performance

### Batch Updates

```javascript
// Bad - multiple reflows
items.forEach(item => {
  const el = document.createElement('div')
  el.textContent = item.name
  container.appendChild(el)  // Reflow each time
})

// Good - single reflow
const fragment = document.createDocumentFragment()
for (const item of items) {
  const el = document.createElement('div')
  el.textContent = item.name
  fragment.appendChild(el)
}
container.appendChild(fragment)  // Single reflow
```

### Event Delegation

```javascript
// Bad - many listeners
cards.forEach(card => {
  card.addEventListener('click', handleClick)
})

// Good - one listener
container.addEventListener('click', (e) => {
  const card = e.target.closest('[data-card-id]')
  if (card) handleCardClick(card.dataset.cardId)
})
```

### Avoid Layout Thrashing

```javascript
// Bad - read/write/read/write (forces multiple reflows)
elements.forEach(el => {
  const height = el.offsetHeight  // Read
  el.style.height = height + 10 + 'px'  // Write
})

// Good - batch reads, then batch writes
const heights = elements.map(el => el.offsetHeight)  // All reads
elements.forEach((el, i) => {
  el.style.height = heights[i] + 10 + 'px'  // All writes
})
```

## Memory

### Clean Up Event Listeners

```javascript
class Component {
  constructor(container) {
    this.container = container
    this.handleClick = this.handleClick.bind(this)
    this.container.addEventListener('click', this.handleClick)
  }
  
  destroy() {
    this.container.removeEventListener('click', this.handleClick)
    this.container = null
  }
}
```

### Avoid Memory Leaks

```javascript
// Bad - closure holds reference
function createHandler(heavyData) {
  return () => {
    console.log(heavyData)  // heavyData never garbage collected
  }
}

// Bad - forgotten intervals
const interval = setInterval(update, 1000)
// Never cleared!

// Good - clean up
class Component {
  start() {
    this.interval = setInterval(() => this.update(), 1000)
  }
  
  destroy() {
    clearInterval(this.interval)
  }
}
```

## Network

### Debounce User Input

```javascript
function debounce(fn, delay) {
  let timeoutId
  return (...args) => {
    clearTimeout(timeoutId)
    timeoutId = setTimeout(() => fn(...args), delay)
  }
}

// Usage
const debouncedSearch = debounce(search, 300)
input.addEventListener('input', (e) => {
  debouncedSearch(e.target.value)
})
```

### Batch API Requests

```javascript
// Bad - many small requests
for (const id of ids) {
  await fetch(`/api/items/${id}`)
}

// Good - single batch request
await fetch('/api/items', {
  method: 'POST',
  body: JSON.stringify({ ids })
})
```

### Lazy Load

```javascript
// Lazy load images
<img loading="lazy" src="..." alt="...">

// Lazy load components
async function loadComponent(name) {
  const module = await import(`./components/${name}/${name}.js`)
  return module.default
}
```

## Database (API)

### Use Indexes

```sql
-- Index columns used in WHERE, JOIN, ORDER BY
CREATE INDEX idx_bookings_parent_id ON bookings(parent_id);
CREATE INDEX idx_bookings_status ON bookings(status);
```

### Select Only Needed Columns

```typescript
// Bad
const users = await db.selectFrom('users').selectAll().execute()

// Good
const users = await db
  .selectFrom('users')
  .select(['id', 'name', 'email'])
  .execute()
```

### Paginate Large Results

```typescript
async function listBookings(page = 1, limit = 20) {
  const offset = (page - 1) * limit
  
  const [items, countResult] = await Promise.all([
    db.selectFrom('bookings')
      .selectAll()
      .limit(limit)
      .offset(offset)
      .execute(),
    db.selectFrom('bookings')
      .select(db.fn.count('id').as('count'))
      .executeTakeFirst()
  ])
  
  return {
    items,
    total: Number(countResult.count),
    page,
    totalPages: Math.ceil(Number(countResult.count) / limit)
  }
}
```

## Checklist

- [ ] No array method chaining on large datasets
- [ ] DOM updates batched (DocumentFragment)
- [ ] Event delegation where possible
- [ ] No layout thrashing
- [ ] Event listeners cleaned up
- [ ] Intervals/timeouts cleared
- [ ] User input debounced
- [ ] API requests batched where possible
- [ ] Images lazy loaded
- [ ] Database queries use indexes
- [ ] Large result sets paginated
