# No Hardcoding

## Never Hardcode

- Environment-specific values (URLs, ports, hosts)
- Secrets (API keys, passwords, tokens)
- User-facing strings (use i18n)
- Magic numbers
- File paths

## Configuration Hierarchy

### 1. Environment Variables (Secrets, Deployment)

```bash
# .env (never commit)
DATABASE_URL=postgresql://...
JWT_SECRET=super-secret-key
REDIS_URL=redis://localhost:6379
```

```typescript
// config/database.ts
export const databaseConfig = {
  url: process.env.DATABASE_URL,
  pool: {
    min: parseInt(process.env.DB_POOL_MIN || '2'),
    max: parseInt(process.env.DB_POOL_MAX || '10')
  }
}
```

### 2. Constants Files (Application Logic)

```typescript
// shared/constants/booking.ts
export const BOOKING_STATUS = {
  PENDING: 'pending',
  CONFIRMED: 'confirmed',
  CANCELLED: 'cancelled',
  COMPLETED: 'completed'
} as const

export const MAX_BOOKING_DAYS_AHEAD = 90
export const MIN_BOOKING_HOURS = 2
export const CANCELLATION_WINDOW_HOURS = 24
```

```javascript
// components/constants.js
export const DEBOUNCE_MS = 300
export const ITEMS_PER_PAGE = 20
export const MAX_FILE_SIZE_MB = 5
```

### 3. i18n for All User-Facing Strings

```javascript
// Never hardcode UI text
// Bad
const title = 'Search for Nannies'
button.textContent = 'Submit'

// Good
import { t } from '../../services/i18n.js'

const title = t('search.title')
button.textContent = t('common.submit')
```

```json
// shared/i18n/locales/en.json
{
  "search": {
    "title": "Search for Nannies",
    "placeholder": "Enter location...",
    "noResults": "No nannies found matching your criteria"
  },
  "common": {
    "submit": "Submit",
    "cancel": "Cancel",
    "save": "Save",
    "delete": "Delete"
  },
  "errors": {
    "required": "This field is required",
    "invalidEmail": "Please enter a valid email"
  }
}
```

### 4. Configuration Objects (Feature Flags, Limits)

```typescript
// config/features.ts
export const features = {
  mbtiTest: {
    enabled: true,
    questionsPerPage: 5
  },
  payments: {
    enabled: process.env.PAYMENTS_ENABLED === 'true',
    providers: ['stripe']
  }
}
```

## API Endpoints

```javascript
// services/api.js
const API_BASE = import.meta.env.VITE_API_URL || '/api'

export const endpoints = {
  auth: {
    login: `${API_BASE}/auth/login`,
    logout: `${API_BASE}/auth/logout`,
    refresh: `${API_BASE}/auth/refresh`
  },
  users: {
    list: `${API_BASE}/users`,
    byId: (id) => `${API_BASE}/users/${id}`
  },
  search: {
    nannies: `${API_BASE}/search/nannies`
  }
}
```

## .env.example

Always provide an example:

```bash
# .env.example
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/nannies

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=change-me-in-production
JWT_EXPIRES_IN=7d

# API
API_PORT=3000
CORS_ORIGIN=http://localhost:5173

# External Services
# STRIPE_SECRET_KEY=sk_test_...
```

## Validation

Validate required config at startup:

```typescript
// config/validate.ts
const required = [
  'DATABASE_URL',
  'JWT_SECRET',
  'REDIS_URL'
]

export function validateConfig() {
  const missing = required.filter(key => !process.env[key])
  
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`)
  }
}
```
