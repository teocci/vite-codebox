# Documentation

## Principle

**Basic documentation for guidance** - not exhaustive, just enough to understand intent.

## JSDoc for Functions

```javascript
/**
 * Search for nannies based on filters.
 * @param {Object} filters - Search filters
 * @param {string} [filters.location] - City or district
 * @param {number} [filters.minRate] - Minimum hourly rate
 * @param {number} [filters.maxRate] - Maximum hourly rate
 * @param {string[]} [filters.services] - Service type IDs
 * @returns {Promise<Nanny[]>} Matching nannies
 */
async function searchNannies(filters) {
  // ...
}
```

## TypeScript - Types Are Documentation

```typescript
// Types make JSDoc redundant for parameters
interface SearchFilters {
  location?: string
  minRate?: number
  maxRate?: number
  services?: string[]
}

// Brief description is still useful
/** Search for nannies based on filters. */
async function searchNannies(filters: SearchFilters): Promise<Nanny[]> {
  // ...
}
```

## When to Document

**Always document:**
- Public API functions
- Complex business logic
- Non-obvious decisions (with why, not what)
- Workarounds and hacks

**Skip documentation for:**
- Obvious getters/setters
- Self-explanatory code
- Private implementation details

## Comment Style

```javascript
// Bad - describes what (obvious from code)
// Loop through items
for (const item of items) {

// Good - describes why (not obvious)
// Process in reverse to maintain dependency order
for (let i = items.length - 1; i >= 0; i--) {

// Good - explains business rule
// Cancellation only allowed 24h before booking
if (hoursUntilBooking < CANCELLATION_WINDOW_HOURS) {
  throw new Error('Cancellation window closed')
}
```

## File Headers

```javascript
/**
 * Booking service - handles booking creation, updates, and cancellation.
 * 
 * Business rules:
 * - Minimum booking duration: 2 hours
 * - Cancellation window: 24 hours before start
 * - Maximum advance booking: 90 days
 */
```

## README per Module (Optional)

For complex modules, a brief README can help:

```markdown
# Bookings Module

## Overview
Handles the booking lifecycle: creation, confirmation, cancellation.

## Key Files
- `bookings.routes.ts` - API endpoints
- `bookings.service.ts` - Business logic
- `bookings.controller.ts` - HTTP handling

## Business Rules
- Min 2 hours per booking
- 24h cancellation window
- Max 90 days advance booking
```

## API Documentation

```typescript
// Document API endpoints in routes file
/**
 * @route GET /api/bookings
 * @query {number} [page=1] - Page number
 * @query {number} [limit=20] - Items per page
 * @query {string} [status] - Filter by status
 * @returns {Booking[]} List of bookings
 * @auth Required
 */
router.get('/', authMiddleware, controller.list)
```

## Avoid

- Outdated comments (worse than no comments)
- Commented-out code (delete it, git has history)
- Redundant comments (`i++ // increment i`)
- Novel-length explanations (keep it brief)
