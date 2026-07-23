# Security First

## Secrets Management

### Never Commit

```gitignore
# .gitignore
.env
.env.*
!.env.example
*.pem
*.key
```

### Environment Variables

```typescript
// Access via process.env (server) or import.meta.env (client)
// Never expose server secrets to client

// Server only
const JWT_SECRET = process.env.JWT_SECRET

// Client (must be prefixed with VITE_)
const API_URL = import.meta.env.VITE_API_URL
```

## Input Validation

### Server Side (Always)

```typescript
// Use Zod or similar for validation
import { z } from 'zod'

const createBookingSchema = z.object({
  nannyId: z.string().uuid(),
  date: z.string().datetime(),
  hours: z.number().min(1).max(12),
  notes: z.string().max(500).optional()
})

// In controller
const result = createBookingSchema.safeParse(req.body)
if (!result.success) {
  return res.status(400).json({ errors: result.error.issues })
}
```

### Client Side (UX, Not Security)

```javascript
// Client validation is for UX only - never trust it for security
function validateEmail(email) {
  const pattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return pattern.test(email)
}
```

## SQL Injection Prevention

```typescript
// Always use parameterized queries
// Bad
const query = `SELECT * FROM users WHERE email = '${email}'`

// Good - parameterized
const result = await db.query(
  'SELECT * FROM users WHERE email = $1',
  [email]
)

// Good - query builder
const user = await db
  .selectFrom('users')
  .where('email', '=', email)
  .executeTakeFirst()
```

## XSS Prevention

```javascript
// Never insert untrusted HTML
// Bad
$element.innerHTML = userContent

// Good - use textContent for text
$element.textContent = userContent

// If HTML needed, sanitize first
import DOMPurify from 'dompurify'

$element.innerHTML = DOMPurify.sanitize(userContent)
```

## CSRF Protection

```typescript
// Use CSRF tokens for state-changing requests
// middleware/csrf.ts
import csrf from 'csurf'

export const csrfProtection = csrf({ cookie: true })

// Include token in forms
// <input type="hidden" name="_csrf" value="{{csrfToken}}">
```

## Authentication

```typescript
// Hash passwords with bcrypt
import bcrypt from 'bcrypt'

const SALT_ROUNDS = 12

async function hashPassword(password: string): Promise<string> {
  return bcrypt.hash(password, SALT_ROUNDS)
}

async function verifyPassword(password: string, hash: string): Promise<boolean> {
  return bcrypt.compare(password, hash)
}
```

## JWT Handling

```typescript
// Short-lived access tokens
const accessToken = jwt.sign(
  { userId: user.id, role: user.role },
  process.env.JWT_SECRET,
  { expiresIn: '15m' }
)

// Longer-lived refresh tokens (stored securely)
const refreshToken = jwt.sign(
  { userId: user.id },
  process.env.JWT_REFRESH_SECRET,
  { expiresIn: '7d' }
)

// Store refresh token in httpOnly cookie
res.cookie('refreshToken', refreshToken, {
  httpOnly: true,
  secure: process.env.NODE_ENV === 'production',
  sameSite: 'strict',
  maxAge: 7 * 24 * 60 * 60 * 1000 // 7 days
})
```

## Rate Limiting

```typescript
// middleware/rate-limit.ts
import rateLimit from 'express-rate-limit'

export const apiLimiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100,
  message: { error: 'Too many requests, please try again later' }
})

export const authLimiter = rateLimit({
  windowMs: 60 * 60 * 1000, // 1 hour
  max: 5, // 5 failed attempts
  message: { error: 'Too many login attempts' }
})
```

## File Upload Security

```typescript
// middleware/upload.ts
import multer from 'multer'
import path from 'path'

const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp']
const MAX_SIZE = 5 * 1024 * 1024 // 5MB

export const upload = multer({
  storage: multer.diskStorage({
    destination: './uploads',
    filename: (req, file, cb) => {
      const uniqueName = `${crypto.randomUUID()}${path.extname(file.originalname)}`
      cb(null, uniqueName)
    }
  }),
  fileFilter: (req, file, cb) => {
    if (ALLOWED_TYPES.includes(file.mimetype)) {
      cb(null, true)
    } else {
      cb(new Error('Invalid file type'))
    }
  },
  limits: { fileSize: MAX_SIZE }
})
```

## Headers

```typescript
// Use helmet for security headers
import helmet from 'helmet'

app.use(helmet())
app.use(helmet.contentSecurityPolicy({
  directives: {
    defaultSrc: ["'self'"],
    styleSrc: ["'self'", "'unsafe-inline'"],
    imgSrc: ["'self'", 'data:', 'https:'],
    scriptSrc: ["'self'"]
  }
}))
```

## Checklist

- [ ] Secrets in environment variables, not code
- [ ] All user input validated server-side
- [ ] Parameterized queries only
- [ ] No innerHTML with untrusted content
- [ ] Passwords hashed with bcrypt (cost ≥12)
- [ ] JWT access tokens short-lived (≤15min)
- [ ] Refresh tokens in httpOnly cookies
- [ ] Rate limiting on auth endpoints
- [ ] File uploads validated (type, size)
- [ ] Security headers via helmet
