# Pre-Commit Checklist

## Analysis
- [ ] Requirements documented
- [ ] Affected files identified
- [ ] Context7 MCP consulted (if third-party APIs involved)

## JavaScript/TypeScript
- [ ] `$` prefix for all DOM element variables
- [ ] Single quotes for strings
- [ ] Backticks for interpolation only
- [ ] No semicolons
- [ ] `const` by default, `let` only when needed
- [ ] `===` not `==`
- [ ] `get` for computed boolean properties
- [ ] `interface` for object contracts
- [ ] `type` for unions/computed types
- [ ] No `any` - use `unknown` with type guards

## CSS
- [ ] Vanilla CSS (no SASS unless justified)
- [ ] CSS variables from design system
- [ ] No magic numbers
- [ ] Mobile-first responsive

## No Hardcoding
- [ ] Environment values in `.env`
- [ ] UI text uses i18n (`t('key')`)
- [ ] Constants in dedicated files
- [ ] API URLs from config

## Security
- [ ] User input validated server-side
- [ ] Parameterized queries only
- [ ] No innerHTML with untrusted content
- [ ] Secrets in environment variables

## No Spaghetti
- [ ] Functions ≤50 lines
- [ ] Single responsibility
- [ ] No code duplication
- [ ] Clear module boundaries

## UI
- [ ] No emojis or Unicode symbols
- [ ] Custom SVG icons only
- [ ] Focus states visible
- [ ] Loading states present
- [ ] Error states clear

## Performance
- [ ] No array method chaining on large data
- [ ] DOM updates batched
- [ ] Event delegation used
- [ ] User input debounced
- [ ] API requests efficient

## i18n
- [ ] All UI text in locale files
- [ ] Both `en.json` and `ru.json` updated
- [ ] Keys follow naming convention

## Project Structure
- [ ] Files in correct directories
- [ ] Shared code in `shared/` package
- [ ] Component has `.js` + `.module.css`
- [ ] API module has routes/controller/service

## Documentation
- [ ] Public functions have JSDoc/TSDoc
- [ ] Complex logic explained (why, not what)
- [ ] No commented-out code