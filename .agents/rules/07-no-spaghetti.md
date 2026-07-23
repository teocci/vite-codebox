# No Spaghetti Code

## Core Principles

- **Single Responsibility** - One purpose per function/class/module
- **Reusability** - Extract common patterns
- **Scalability** - Structure that grows cleanly
- **Explicit Dependencies** - No hidden coupling

## Module Structure (Backend)

```
modules/
└── bookings/
    ├── bookings.routes.ts      # Route definitions only
    ├── bookings.controller.ts  # HTTP handling, validation
    ├── bookings.service.ts     # Business logic
    └── bookings.types.ts       # Types for this module
```

```typescript
// bookings.routes.ts - ONLY route definitions
import { Router } from 'express'
import { BookingsController } from './bookings.controller'
import { authMiddleware } from '../../middleware/auth'

const router = Router()
const controller = new BookingsController()

router.get('/', authMiddleware, controller.list)
router.post('/', authMiddleware, controller.create)
router.get('/:id', authMiddleware, controller.getById)

export default router
```

```typescript
// bookings.controller.ts - HTTP layer only
export class BookingsController {
  private service = new BookingsService()
  
  list = async (req: Request, res: Response) => {
    const { page, limit } = req.query
    const result = await this.service.list({ page, limit, userId: req.user.id })
    res.json(result)
  }
  
  create = async (req: Request, res: Response) => {
    const validation = createBookingSchema.safeParse(req.body)
    if (!validation.success) {
      return res.status(400).json({ errors: validation.error.issues })
    }
    
    const booking = await this.service.create(validation.data, req.user.id)
    res.status(201).json(booking)
  }
}
```

```typescript
// bookings.service.ts - Business logic only
export class BookingsService {
  async create(data: CreateBookingInput, userId: string): Promise<Booking> {
    // Validate business rules
    await this.validateAvailability(data.nannyId, data.date)
    await this.validateNoConflicts(userId, data.date)
    
    // Create booking
    const booking = await db
      .insertInto('bookings')
      .values({ ...data, parentId: userId, status: 'pending' })
      .returningAll()
      .executeTakeFirstOrThrow()
    
    // Side effects
    await notificationService.sendBookingRequest(booking)
    
    return booking
  }
}
```

## Component Structure (Frontend)

```
components/
└── NannyCard/
    ├── NannyCard.js          # Component logic
    └── NannyCard.module.css  # Styles
```

```javascript
// NannyCard.js - Clean component with $ prefix for DOM
import BaseComponent from '../base/BaseComponent.js'
import styles from './NannyCard.module.css'
import { t } from '../../services/i18n.js'
import { formatCurrency } from '../../utils/format.js'

export default class NannyCard extends BaseComponent {
    static TAG = 'nanny-card'

    /** @type {Object} */
    nanny

    /** @type {Function} */
    onSelect

    constructor($element, nanny, options = {}) {
        super($element)

        this.nanny = nanny
        this.onSelect = options.onSelect

        this.render()
        this.initListeners()
    }

    get isSelected() {
        return this.$element.classList.contains(styles.selected)
    }

    render() {
        const { nanny } = this
        this.$element.className = styles.card
        this.$element.innerHTML = this.template()

        // Cache DOM references with $ prefix
        this.$avatar = this.$element.querySelector(`.${styles.avatar}`)
        this.$name = this.$element.querySelector(`.${styles.name}`)
        this.$rate = this.$element.querySelector(`.${styles.rate}`)
    }

    template() {
        const { nanny } = this
        return `
            <img class="${styles.avatar}" src="${nanny.avatarUrl}" alt="">
            <div class="${styles.info}">
                <h3 class="${styles.name}">${nanny.name}</h3>
                <p class="${styles.rate}">${formatCurrency(nanny.hourlyRate)}/${t('common.hour')}</p>
            </div>
        `
    }

    initListeners() {
        this.$element.addEventListener('click', () => {
            this.onSelect?.(this.nanny.id)
        })
    }

    destroy() {
        this.$element?.remove()
        this.$element = null
    }
}
```

## Function Size Limits

- **Target:** ≤30 lines per function
- **Max:** 50 lines (with good reason)
- **If larger:** Split into helpers

```javascript
// Bad - doing too much
async function handleFormSubmit(event) {
    event.preventDefault()
    // 80 lines of validation, API calls, DOM updates, error handling...
}

// Good - separated concerns
async function handleFormSubmit(event) {
    event.preventDefault()

    const $form = event.target
    const data = getFormData($form)
    const errors = validateFormData(data)

    if (errors.length > 0) {
        displayErrors($form, errors)
        return
    }

    try {
        setLoadingState($form, true)
        const result = await submitBooking(data)
        handleSuccess(result)
    } catch (error) {
        handleError(error)
    } finally {
        setLoadingState($form, false)
    }
}
```

## No Duplication (DRY)

```javascript
// Bad - duplicated logic
class NannyCard {
    formatRate() {
        return `${this.nanny.hourlyRate} ₽/час`
    }
}

class NannyProfile {
    formatRate() {
        return `${this.nanny.hourlyRate} ₽/час`  // Same logic!
    }
}

// Good - shared utility
// utils/format.js
export function formatCurrency(amount, currency = 'RUB') {
    return new Intl.NumberFormat('ru-RU', {
        style: 'currency',
        currency
    }).format(amount)
}
```

## Dependency Injection

```typescript
// Bad - hidden dependency
class BookingsService {
    async create(data) {
        const db = new Database()  // Hidden, untestable
        // ...
    }
}

// Good - injected dependency
class BookingsService {
    constructor(private db: Database) {}

    async create(data) {
        return this.db.insertInto('bookings')...
    }
}

// Usage
const db = new Database()
const service = new BookingsService(db)
```

## Avoid

- Functions >50 lines
- More than 3 levels of nesting
- Callbacks inside callbacks (callback hell)
- Circular dependencies between modules
- God objects/classes that do everything
- Copy-paste code
- Semicolons and double quotes