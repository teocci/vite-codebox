# UI Rules

## No Emojis or Generic Icons

**Never use** in the UI:
- Emojis (😀, 🏠, ✅)
- Emoticons
- Generic Unicode symbols (★, ●, ▶)
- U+ codepoint symbols

**Always use** custom SVG icons that:
- Match the design system (size, stroke, color)
- Clearly represent the feature/action
- Scale cleanly
- Support theming via CSS variables

## SVG Icon Pattern

### Inline SVG Component

```javascript
// components/icons/Icon.js
export function Icon({ name, size = 24, className = '' }) {
  const icons = {
    search: `<path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>`,
    user: `<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2M12 11a4 4 0 100-8 4 4 0 000 8z"/>`,
    calendar: `<path d="M8 2v4M16 2v4M3 10h18M5 4h14a2 2 0 012 2v14a2 2 0 01-2 2H5a2 2 0 01-2-2V6a2 2 0 012-2z"/>`,
    star: `<path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/>`,
    check: `<path d="M20 6L9 17l-5-5"/>`,
    x: `<path d="M18 6L6 18M6 6l12 12"/>`,
    chevronRight: `<path d="M9 18l6-6-6-6"/>`,
    heart: `<path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/>`
  }
  
  const path = icons[name]
  if (!path) {
    console.warn(`Icon not found: ${name}`)
    return ''
  }
  
  return `
    <svg 
      class="icon ${className}" 
      width="${size}" 
      height="${size}" 
      viewBox="0 0 24 24" 
      fill="none" 
      stroke="currentColor" 
      stroke-width="2" 
      stroke-linecap="round" 
      stroke-linejoin="round"
    >
      ${path}
    </svg>
  `
}
```

### Usage

```javascript
import { Icon } from '../icons/Icon.js'

// In template
`<button class="${styles.button}">
  ${Icon({ name: 'search', size: 20 })}
  <span>${t('search.button')}</span>
</button>`
```

### CSS for Icons

```css
/* base.css */
.icon {
  flex-shrink: 0;
  color: currentColor;
}

/* Sizes */
.iconSm { width: 16px; height: 16px; }
.iconMd { width: 20px; height: 20px; }
.iconLg { width: 24px; height: 24px; }

/* In buttons */
.button .icon {
  margin-right: var(--space-xs);
}
```

## Accessibility

### ARIA Labels

```javascript
// Icons without visible text need labels
`<button aria-label="${t('actions.close')}">
  ${Icon({ name: 'x' })}
</button>`

// Icons with visible text - hide icon from screen readers
`<button>
  <span aria-hidden="true">${Icon({ name: 'search' })}</span>
  <span>${t('search.button')}</span>
</button>`
```

### Focus States

```css
/* Always visible focus indicators */
:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

/* Remove default, keep visible */
button:focus {
  outline: none;
}

button:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}
```

### Color Contrast

- Normal text: minimum 4.5:1 contrast ratio
- Large text (18px+): minimum 3:1 contrast ratio
- Interactive elements: minimum 3:1 against background

### Semantic HTML

```html
<!-- Use proper elements -->
<button>Click me</button>        <!-- Not <div onclick> -->
<a href="/page">Go to page</a>   <!-- Not <span onclick> -->
<nav>...</nav>                   <!-- Not <div class="nav"> -->
<main>...</main>                 <!-- Not <div class="main"> -->
```

## Loading States

```javascript
// Always show loading feedback
function setLoadingState(button, isLoading) {
  button.disabled = isLoading
  button.setAttribute('aria-busy', isLoading)
  
  if (isLoading) {
    button.dataset.originalText = button.textContent
    button.innerHTML = `
      ${Icon({ name: 'spinner', className: 'animate-spin' })}
      <span>${t('common.loading')}</span>
    `
  } else {
    button.textContent = button.dataset.originalText
  }
}
```

## Error States

```css
/* Clear error indication */
.inputError {
  border-color: var(--color-error);
}

.errorMessage {
  color: var(--color-error);
  font-size: var(--font-size-sm);
  margin-top: var(--space-xs);
}

/* Don't rely on color alone */
.inputError::before {
  content: '';
  /* Add icon or other indicator */
}
```

## Checklist

- [ ] No emojis or Unicode symbols in UI
- [ ] All icons are custom SVGs
- [ ] Icons match design system (size, stroke, color)
- [ ] All interactive elements are focusable
- [ ] Focus states are visible
- [ ] Color contrast meets WCAG AA
- [ ] Semantic HTML elements used
- [ ] Loading states provide feedback
- [ ] Error messages are clear and accessible
