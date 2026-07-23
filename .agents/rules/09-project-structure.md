# Project Structure (Nannies Monorepo)

## Directory Layout

```
nannies/
├── apps/
│   ├── api/                    # Express backend
│   │   └── src/
│   │       ├── config/         # Database, Redis config
│   │       ├── db/
│   │       │   ├── migrations/ # Database migrations
│   │       │   └── seeds/      # Seed data
│   │       ├── middleware/     # Auth, rate-limit, upload
│   │       ├── modules/        # Feature modules
│   │       │   └── [feature]/
│   │       │       ├── [feature].routes.ts
│   │       │       ├── [feature].controller.ts
│   │       │       └── [feature].service.ts
│   │       └── websocket/      # Socket.io
│   │
│   └── web/                    # Vanilla JS frontend
│       └── src/
│           ├── components/     # Reusable UI components
│           │   └── [Component]/
│           │       ├── [Component].js
│           │       └── [Component].module.css
│           ├── pages/          # Page-level components
│           │   └── [Feature]/
│           │       └── [Page]/
│           │           ├── [Page].js
│           │           └── [Page].module.css
│           ├── services/       # API, i18n
│           ├── store/          # State management
│           ├── router/         # Client-side routing
│           └── styles/         # Global CSS
│
├── shared/
│   ├── i18n/                   # Translations
│   │   └── src/locales/
│   │       ├── en.json
│   │       └── ru.json
│   └── shared/                 # Shared types, constants
│       └── src/
│           ├── constants/      # Shared constants
│           ├── types/          # TypeScript interfaces
│           └── validators/     # Shared validation schemas
│
└── .claude/
    ├── rules/                  # Claude Code rules
    └── agents/                 # Custom agents
```

## Module Pattern (API)

Each feature module follows this pattern:

```typescript
// modules/bookings/bookings.routes.ts
import { Router } from 'express'
import { BookingsController } from './bookings.controller'

const router = Router()
const controller = new BookingsController()

router.get('/', controller.list)
router.post('/', controller.create)

export default router
```

```typescript
// modules/bookings/bookings.controller.ts
export class BookingsController {
  private service = new BookingsService()
  
  list = async (req: Request, res: Response) => {
    // Validation, call service, return response
  }
}
```

```typescript
// modules/bookings/bookings.service.ts
export class BookingsService {
  async list(params: ListParams) {
    // Business logic only
  }
}
```

## Component Pattern (Web)

Each component is self-contained:

```javascript
// components/NannyCard/NannyCard.js
import styles from './NannyCard.module.css'
import { t } from '../../services/i18n.js'

export class NannyCard {
  constructor(container, data, options = {}) {
    this.container = container
    this.data = data
    this.options = options
    
    this.render()
    this.bindEvents()
  }
  
  render() { /* ... */ }
  bindEvents() { /* ... */ }
  destroy() { /* ... */ }
}
```

## Shared Package Usage

```typescript
// In apps/api
import { BOOKING_STATUS } from '@nannies/shared'
import { t } from '@nannies/i18n'

// In apps/web
import { BOOKING_STATUS } from '@nannies/shared'
```

## File Naming

| Type | Pattern | Example |
|------|---------|---------|
| Component | PascalCase | `NannyCard.js` |
| Module | kebab-case | `bookings.service.ts` |
| Style | module.css | `NannyCard.module.css` |
| Constant | kebab-case | `booking.ts` |
| Type | kebab-case | `booking.ts` |

## New Feature Checklist

When adding a new feature:

1. **Shared types** → `shared/shared/src/types/`
2. **Constants** → `shared/shared/src/constants/`
3. **i18n keys** → `shared/i18n/src/locales/en.json` + `ru.json`
4. **API module** → `apps/api/src/modules/[feature]/`
5. **Web components** → `apps/web/src/components/[Feature]/`
6. **Web pages** → `apps/web/src/pages/[Feature]/`
7. **Routes** → `apps/web/src/router/routes.js`
