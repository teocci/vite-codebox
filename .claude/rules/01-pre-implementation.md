# Pre-Implementation Analysis

Before writing any code, create a brief analysis:

1. **Requirements** - What exactly needs to be built
2. **Affected files** - Which existing modules/components will change
3. **New files** - What new files need to be created
4. **Dependencies** - Any new packages needed (justify each one)
5. **Performance impact** - How will this affect bundle size, runtime
6. **i18n keys** - What new translation strings are needed

## MCP Integration

If the implementation depends on third-party library/framework/API specifics, consult **Context7 MCP first** and base code/setup/config on retrieved docs.

Skip only if:
- Pure language/algorithm work
- User explicitly opts out

## Analysis Format

```markdown
## Analysis: [Feature Name]

### Requirements
- ...

### Files to Modify
- `apps/api/src/modules/...`
- `apps/web/src/pages/...`

### New Files
- `apps/web/src/components/NewComponent/NewComponent.js`
- `apps/web/src/components/NewComponent/NewComponent.module.css`

### Dependencies
None required (or justify each addition)

### Performance Notes
- ...

### i18n Keys
- `feature.title`
- `feature.description`
```
