# TypeScript Rules

## Interface vs Type: Two Clear Rules

### Rule 1: Use `interface` for Object-Shape Contracts

Use `interface` when the type represents the shape of an object that is a "contract" boundary:
- DTOs (Data Transfer Objects)
- Domain entities
- Public config
- Component props
- Service contracts

Prefer `extends` for composition.

```typescript
// Domain entities
interface User {
  id: string
  name: string
  email: string
}

interface AdminUser extends User {
  role: 'admin'
  permissions: string[]
}

// Service contracts
interface AuthService {
  login(credentials: LoginCredentials): Promise<AuthResult>
  logout(): Promise<void>
  refreshToken(): Promise<string>
}

// API responses (DTOs)
interface ApiResponse<T> {
  data: T
  meta: {
    total: number
    page: number
  }
}

// Config shapes
interface DatabaseConfig {
  host: string
  port: number
  database: string
}
```

### Rule 2: Use `type` for Type Algebra and Computed Types

Use `type` when the definition requires:
- Unions / intersections
- Discriminated unions
- Mapped types / conditional types
- Template literal types
- Utility/composed "computed" types
- Function type aliases (when no object contract)

```typescript
// Unions
type Id = string | number
type Status = 'pending' | 'active' | 'completed' | 'cancelled'
type Theme = 'light' | 'dark' | 'system'

// Discriminated unions
type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: string }

type WebSocketMessage =
  | { type: 'connect'; userId: string }
  | { type: 'message'; content: string; roomId: string }
  | { type: 'disconnect'; reason?: string }

// Mapped / conditional types
type ReadonlyDeep<T> = {
  readonly [K in keyof T]: T[K] extends object ? ReadonlyDeep<T[K]> : T[K]
}

type Nullable<T> = { [K in keyof T]: T[K] | null }

// Function types
type Comparator<T> = (a: T, b: T) => number
type EventHandler<E> = (event: E) => void
type AsyncFn<T, R> = (arg: T) => Promise<R>

// Template literals
type HttpMethod = 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH'
type ApiEndpoint = `/api/${string}`
type EventName = `on${Capitalize<string>}`

// Utility compositions
type PartialBy<T, K extends keyof T> = Omit<T, K> & Partial<Pick<T, K>>
type RequiredBy<T, K extends keyof T> = T & Required<Pick<T, K>>
```

## Strict Typing Practices

```typescript
// Always type function parameters and returns
function calculateTotal(items: CartItem[], discount: number): number {
  // ...
}

// Use const assertions for literal types
const ROUTES = {
  home: '/',
  search: '/search',
  profile: '/profile'
} as const

type Route = typeof ROUTES[keyof typeof ROUTES]

// Prefer unknown over any
function parseJson(input: string): unknown {
  return JSON.parse(input)
}

// Use type guards for narrowing
function isUser(value: unknown): value is User {
  return (
    typeof value === 'object' &&
    value !== null &&
    'id' in value &&
    'email' in value
  )
}
```

## Avoid

- `any` - use `unknown` and narrow with type guards
- Non-null assertion (`!`) without justification
- Type assertions (`as`) when type guards work
- Overly complex generic chains (simplify or document)
- `interface` for unions or computed types
- `type` for simple object contracts
