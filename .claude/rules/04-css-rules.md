# CSS Rules

## Core Principle

**Vanilla CSS preferred.** Modern CSS (custom properties, nesting, container queries) covers most needs. Avoid SASS/LESS unless there's a compelling reason.

## When Preprocessors Are Justified

Only consider SASS/LESS for:
- Complex mathematical calculations not feasible with `calc()`
- Large-scale design system with deep theming requirements
- Legacy codebase already using it

For this project: **CSS Modules + CSS Custom Properties** is sufficient.

## File Organization

```
ComponentName/
├── ComponentName.js
└── ComponentName.module.css
```

## CSS Custom Properties (Variables)

Define in `variables.css`, use everywhere:

```css
/* variables.css */
:root {
  /* Colors */
  --color-primary: #2563eb;
  --color-primary-hover: #1d4ed8;
  --color-text: #1f2937;
  --color-text-muted: #6b7280;
  --color-background: #ffffff;
  --color-border: #e5e7eb;
  --color-error: #dc2626;
  --color-success: #16a34a;
  
  /* Spacing (consistent scale) */
  --space-xs: 0.25rem;   /* 4px */
  --space-sm: 0.5rem;    /* 8px */
  --space-md: 1rem;      /* 16px */
  --space-lg: 1.5rem;    /* 24px */
  --space-xl: 2rem;      /* 32px */
  
  /* Typography */
  --font-family: system-ui, -apple-system, sans-serif;
  --font-size-sm: 0.875rem;
  --font-size-base: 1rem;
  --font-size-lg: 1.125rem;
  --font-size-xl: 1.25rem;
  
  /* Borders */
  --radius-sm: 0.25rem;
  --radius-md: 0.5rem;
  --radius-lg: 0.75rem;
  --radius-full: 9999px;
  
  /* Shadows */
  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px rgba(0, 0, 0, 0.1);
  
  /* Transitions */
  --transition-fast: 150ms ease;
  --transition-base: 200ms ease;
}
```

## CSS Modules Pattern

```css
/* NannyCard.module.css */
.card {
  display: flex;
  gap: var(--space-md);
  padding: var(--space-lg);
  background: var(--color-background);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: box-shadow var(--transition-fast);
}

.card:hover {
  box-shadow: var(--shadow-md);
}

.avatar {
  width: 4rem;
  height: 4rem;
  border-radius: var(--radius-full);
  object-fit: cover;
}

.name {
  font-size: var(--font-size-lg);
  font-weight: 600;
  color: var(--color-text);
}

.rate {
  color: var(--color-text-muted);
  font-size: var(--font-size-sm);
}

/* State variants */
.cardSelected {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 1px var(--color-primary);
}

.cardDisabled {
  opacity: 0.6;
  pointer-events: none;
}
```

## Naming Conventions

```css
/* Component root */
.card { }

/* Elements within component */
.cardHeader { }
.cardBody { }
.cardFooter { }

/* State modifiers */
.cardActive { }
.cardDisabled { }
.cardLoading { }

/* Size variants */
.cardSm { }
.cardLg { }
```

## Performance

```css
/* Prefer transform/opacity for animations (GPU accelerated) */
.fadeIn {
  opacity: 0;
  transform: translateY(10px);
  transition: opacity var(--transition-base), transform var(--transition-base);
}

.fadeInVisible {
  opacity: 1;
  transform: translateY(0);
}

/* Avoid animating layout properties */
/* Bad: width, height, margin, padding, top, left */
/* Good: transform, opacity */

/* Use will-change sparingly */
.heavyAnimation {
  will-change: transform;
}
```

## Responsive Design

```css
/* Mobile-first breakpoints */
.grid {
  display: grid;
  gap: var(--space-md);
  grid-template-columns: 1fr;
}

@media (min-width: 640px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (min-width: 1024px) {
  .grid {
    grid-template-columns: repeat(3, 1fr);
  }
}
```

## Avoid

- Preprocessors (SASS/LESS) unless justified
- `!important` (fix specificity instead)
- Deep nesting (max 3 levels)
- Magic numbers (use variables)
- ID selectors for styling
- Inline styles except for truly dynamic values
- `@import` in CSS (use bundler imports)
