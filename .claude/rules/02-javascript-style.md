# JavaScript ES6+ Style

## Core Principles

- **Vanilla JS preferred** - No frameworks unless absolutely necessary
- **No magic** - Explicit over implicit, no black boxes
- **Understand the cost** - Every decision has performance implications

## Formatting Rules

- **Single quotes** for strings: `'hello'`
- **Backticks** for interpolation: `` `${name}.png` ``
- **No semicolons** - Rely on ASI (Automatic Semicolon Insertion)
- **No trailing commas** in single-line, **trailing commas** in multi-line

```javascript
// Correct
const name = 'viewer'
const filename = `${name}.png`
const elementId = `image-${hashID()}`

// Incorrect
const name = "viewer";
const filename = name + ".png";
```

## $ Prefix for DOM Elements

**Always prefix DOM element variables with `$`** to visually distinguish them from data/components:

```javascript
// DOM elements - prefixed with $
const $viewer = document.getElementById('viewer')
const $sidebar = document.querySelector('.sidebar')
const $buttons = document.querySelectorAll('.btn')

// Components/data - no prefix
const viewer = new ViewerComponent($viewer)
const sidebar = new SidebarComponent($sidebar)
const config = { theme: 'dark' }

// Clear distinction in usage
$viewer.classList.add('active')    // DOM manipulation
viewer.loadContent(data)           // Component method
```

### In Classes

```javascript
export default class BaseComponent {
    /** @type {HTMLElement} */
    $element

    /** @type {HTMLElement} */
    $placeholder

    constructor($element) {
        this.$element = $element ?? null
        this.$placeholder = $element ?? null
    }

    get dom() {
        return this.$element
    }

    get holder() {
        return this.$placeholder
    }

    set dom($element) {
        this.$element = $element
    }
}
```

### In Methods

```javascript
// Parameter is a DOM element - use $
initElements($container) {
    this.$header = $container.querySelector('.header')
    this.$content = $container.querySelector('.content')
}

// Creating elements
createElement() {
    const $wrapper = document.createElement('div')
    $wrapper.className = styles.wrapper
    return $wrapper
}
```

## Getters for Boolean Properties

Use `get` for computed boolean values - cleaner API:

```javascript
export default class ViewerComponent {
    get isActive() {
        return this.view?.isActive ?? false
    }

    get isLoading() {
        return this.state === 'loading'
    }

    get hasContent() {
        return this.items.length > 0
    }

    get canSubmit() {
        return this.isValid && !this.isLoading
    }
}

// Usage - reads naturally
if (viewer.isActive) { ... }
if (form.canSubmit) { ... }
```

## Static Singleton Pattern

```javascript
export default class ViewerModule extends BaseComponent {
    static TAG = 'viewer'

    static get instance() {
        this._instance = this._instance ?? new ViewerModule()
        return this._instance
    }

    /** @type {ToolbarComponent} */
    toolbar

    /** @type {ViewerComponent} */
    viewer

    constructor($element) {
        super($element)
        this.initElements()
        this.initListeners()
    }
}
```

## Module Structure

```javascript
// Component.js - Standard structure
import BaseComponent from './base-component.js'
import { apiService } from '../../services/api.js'
import { t } from '../../services/i18n.js'

const CONSTANTS = {
    MAX_ITEMS: 100,
    DEBOUNCE_MS: 300
}

export default class Component extends BaseComponent {
    static TAG = 'component'

    /** @type {HTMLElement} */
    $content

    constructor($element, options = {}) {
        super($element)

        this.options = { ...DEFAULTS, ...options }
        this.state = {}

        this.init()
    }

    init() { ... }
    render() { ... }
    destroy() { ... }
}
```

## Iteration: Know the Cost

| Method | Use When | Cost |
|--------|----------|------|
| `for` | Performance critical, need `break`/`continue`, index access | Fastest |
| `for...of` | Iterating values, readability over micro-optimization | ~Same as for |
| `forEach` | Side effects, no early exit needed | Slight overhead, no break |
| `map` | Transforming to new array | Creates new array |
| `filter` | Subsetting | Creates new array |
| `reduce` | Aggregation | Single pass, but often misused |

```javascript
// Performance critical (large datasets) - use for
for (let i = 0; i < items.length; i++) {
    if (items[i].match) break
}

// Readability (small arrays) - for...of is fine
for (const item of items) {
    process(item)
}

// Avoid chaining on large datasets
// Bad - 3 iterations, 2 intermediate arrays
const result = items.filter(x => x.active).map(x => x.id).slice(0, 10)

// Better - single pass
const result = []
for (const item of items) {
    if (item.active) {
        result.push(item.id)
        if (result.length >= 10) break
    }
}
```

## DOM Manipulation

```javascript
// Batch DOM updates - minimize reflows
const fragment = document.createDocumentFragment()
for (const item of items) {
    const $el = this.createItemElement(item)
    fragment.appendChild($el)
}
this.$container.appendChild(fragment)

// Use event delegation
this.$container.addEventListener('click', e => {
    const $card = e.target.closest('[data-id]')
    if ($card) this.handleCardClick($card.dataset.id)
})
```

## Async Patterns

```javascript
// Prefer async/await over .then chains
async fetchData() {
    try {
        const response = await apiService.get('/endpoint')
        return response.data
    } catch (error) {
        console.error('Fetch failed:', error)
        throw error
    }
}

// Parallel when independent
const [users, services] = await Promise.all([
    apiService.get('/users'),
    apiService.get('/services')
])

// Sequential when dependent
const user = await apiService.get(`/users/${id}`)
const profile = await apiService.get(`/profiles/${user.profileId}`)
```

## Nullish Coalescing & Optional Chaining

```javascript
// Prefer ?? over || for defaults (handles 0 and '' correctly)
const count = input ?? 0
const name = user?.profile?.name ?? 'Anonymous'

// Optional chaining for safe access
const isActive = this.view?.isActive
const handler = this.options?.onSelect
handler?.(item)
```

## Avoid

- `var` - always `const`, use `let` only when reassignment needed
- `==` - always `===`
- Nested ternaries
- `arguments` object - use rest parameters
- `with` statement
- `eval()`
- Semicolons (rely on ASI)
- Double quotes for strings (use single quotes)