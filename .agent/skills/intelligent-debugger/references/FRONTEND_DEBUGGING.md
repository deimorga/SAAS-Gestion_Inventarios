# Frontend Debugging Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Browser Developer Tools](#browser-developer-tools)
3. [Console Debugging](#console-debugging)
4. [Network Debugging](#network-debugging)
5. [React/Vue/Angular Debugging](#reactvueangular-debugging)
6. [CSS and Layout Issues](#css-and-layout-issues)
7. [JavaScript Errors](#javascript-errors)
8. [Performance Issues](#performance-issues)
9. [Mobile and Responsive Debugging](#mobile-and-responsive-debugging)
10. [Common Frontend Bugs](#common-frontend-bugs)

---

## Introduction

Frontend debugging involves diagnosing issues in HTML, CSS, JavaScript, and user interactions. The browser's Developer Tools are your primary debugging interface.

**Key Frontend Issues:**
- JavaScript errors and exceptions
- API call failures
- Rendering problems
- CSS layout issues
- Performance bottlenecks
- Cross-browser incompatibilities

---

## Browser Developer Tools

### Opening DevTools

**Chrome/Edge:**
- `F12` or `Ctrl+Shift+I` (Windows/Linux)
- `Cmd+Option+I` (Mac)
- Right-click → Inspect

**Firefox:**
- `F12` or `Ctrl+Shift+I`
- Tools → Browser Tools → Web Developer Tools

**Safari:**
- Enable Developer menu: Preferences → Advanced → Show Develop menu
- `Cmd+Option+I`

### Essential DevTools Tabs

**1. Elements/Inspector Tab**
- Inspect HTML structure
- Modify CSS in real-time
- View computed styles
- Check element dimensions

**2. Console Tab**
- JavaScript errors
- Console.log output
- Execute JavaScript
- Monitor warnings

**3. Sources/Debugger Tab**
- Set breakpoints
- Step through code
- Watch variables
- View call stack

**4. Network Tab**
- Monitor HTTP requests
- Check request/response
- View timing
- Inspect headers

**5. Performance Tab**
- Record performance
- Analyze frame rate
- Identify bottlenecks
- Profile JavaScript

**6. Application Tab**
- LocalStorage/SessionStorage
- Cookies
- IndexedDB
- Service Workers

---

## Console Debugging

### Console Methods

```javascript
// Basic logging
console.log('Simple message');
console.log('Multiple', 'values', { key: 'value' });

// Different levels
console.info('Information message');
console.warn('Warning message');
console.error('Error message');
console.debug('Debug message');

// Styled output
console.log('%cStyled text', 'color: blue; font-size: 20px;');

// Group messages
console.group('User Data');
console.log('Name: John');
console.log('Age: 30');
console.groupEnd();

// Table format (great for arrays of objects)
console.table([
    { name: 'John', age: 30 },
    { name: 'Jane', age: 25 }
]);

// Timing
console.time('operation');
// ... code to time ...
console.timeEnd('operation');

// Stack trace
console.trace('Trace point');

// Count calls
console.count('API call');  // API call: 1
console.count('API call');  // API call: 2

// Assert
console.assert(x > 10, 'X should be greater than 10');

// Clear console
console.clear();
```

### Strategic Logging

```javascript
// Log function entry/exit
function processData(data) {
    console.log('processData called with:', data);
    
    try {
        const result = transform(data);
        console.log('Transform result:', result);
        return result;
    } catch (error) {
        console.error('Error in processData:', error);
        throw error;
    }
}

// Log state changes
const prevState = { ...state };
setState(newState);
console.log('State changed:', {
    before: prevState,
    after: state,
    diff: stateDiff(prevState, state)
});

// Conditional logging
const DEBUG = true;
const log = DEBUG ? console.log : () => {};
log('Debug message');  // Only logs if DEBUG is true
```

### Console Filtering

```javascript
// Use prefixes for easy filtering
console.log('[API]', 'User data fetched');
console.log('[STATE]', 'Counter updated');
console.log('[ERROR]', 'Failed to save');

// Then filter in console: "[API]" or "[ERROR]"
```

---

## Network Debugging

### Analyzing Network Requests

**In Network Tab:**
1. Open Network tab
2. Reload page or trigger request
3. Click request to see details

**Request Information:**
- **Headers**: Request/response headers
- **Preview**: Formatted response
- **Response**: Raw response data
- **Timing**: Request breakdown
- **Cookies**: Request/response cookies

### Common Network Issues

**1. CORS Errors**
```
Error: No 'Access-Control-Allow-Origin' header

Debugging:
1. Check request origin vs API domain
2. Verify CORS headers on server
3. Check preflight OPTIONS request
4. Review allowed origins configuration
```

**Fix CORS (Server Side):**
```javascript
// Express.js
app.use((req, res, next) => {
    res.header('Access-Control-Allow-Origin', '*');
    res.header('Access-Control-Allow-Methods', 'GET,POST,PUT,DELETE');
    res.header('Access-Control-Allow-Headers', 'Content-Type,Authorization');
    next();
});
```

**2. 404 Not Found**
```
Debugging:
1. Check URL spelling in code
2. Verify API endpoint exists
3. Check for hardcoded URLs
4. Review route configuration
```

**3. 401 Unauthorized / 403 Forbidden**
```
Debugging:
1. Check authentication token
2. Verify token expiration
3. Check authorization headers
4. Review user permissions
```

**4. 500 Server Error**
```
Debugging:
1. Check browser console for details
2. Review server logs
3. Verify request payload format
4. Test with curl/Postman
```

### Network Debugging Tools

**Fetch Debugging:**
```javascript
// Add logging to fetch
const originalFetch = window.fetch;
window.fetch = function(...args) {
    console.log('Fetch called:', args[0]);
    return originalFetch.apply(this, args)
        .then(response => {
            console.log('Fetch response:', response.status, args[0]);
            return response;
        })
        .catch(error => {
            console.error('Fetch error:', args[0], error);
            throw error;
        });
};
```

**Axios Interceptors:**
```javascript
// Request interceptor
axios.interceptors.request.use(
    config => {
        console.log('Request:', config.method, config.url);
        return config;
    },
    error => {
        console.error('Request error:', error);
        return Promise.reject(error);
    }
);

// Response interceptor
axios.interceptors.response.use(
    response => {
        console.log('Response:', response.status, response.config.url);
        return response;
    },
    error => {
        console.error('Response error:', error.response?.status, error.config.url);
        return Promise.reject(error);
    }
);
```

---

## React/Vue/Angular Debugging

### React DevTools

**Installation:**
- Chrome/Firefox extension: "React Developer Tools"

**Features:**
- Component tree inspection
- Props and state viewing
- Performance profiling
- Hook inspection

**Usage:**
```javascript
// Inspect component state
// 1. Open React DevTools
// 2. Select component
// 3. View props, state, hooks in right panel

// Profile performance
// 1. Open Profiler tab
// 2. Click Record
// 3. Interact with app
// 4. Stop recording
// 5. Analyze renders and timing
```

**Common React Issues:**

**1. Component Not Re-rendering**
```javascript
// Problem: Mutating state directly
const [items, setItems] = useState([1, 2, 3]);
items.push(4);  // ❌ Mutation doesn't trigger re-render

// Solution: Create new array
setItems([...items, 4]);  // ✅ New reference triggers re-render
```

**2. Infinite Re-render Loop**
```javascript
// Problem: setState in render
function Component() {
    const [count, setCount] = useState(0);
    setCount(count + 1);  // ❌ Infinite loop!
    return <div>{count}</div>;
}

// Solution: Use effect or event handler
function Component() {
    const [count, setCount] = useState(0);
    
    useEffect(() => {
        setCount(1);  // ✅ Runs once
    }, []);
    
    return <div>{count}</div>;
}
```

**3. useEffect Dependencies**
```javascript
// Problem: Missing dependencies
useEffect(() => {
    fetchData(userId);  // ❌ userId not in deps
}, []);

// Solution: Include all dependencies
useEffect(() => {
    fetchData(userId);  // ✅ Re-runs when userId changes
}, [userId]);
```

### Vue DevTools

**Installation:**
- Browser extension: "Vue.js devtools"

**Features:**
- Component hierarchy
- Vuex state inspection
- Event tracking
- Performance monitoring

**Common Vue Issues:**

**1. Reactivity Issues**
```javascript
// Problem: Adding property after creation
data() {
    return { user: {} };
}
this.user.name = 'John';  // ❌ Not reactive

// Solution: Use Vue.set or spread
Vue.set(this.user, 'name', 'John');  // ✅ Vue 2
this.user = { ...this.user, name: 'John' };  // ✅ Both
```

**2. Template Syntax Errors**
```vue
<!-- Problem: Using = instead of : -->
<div class="active: isActive"></div>  ❌

<!-- Solution: Use v-bind or : -->
<div :class="{ active: isActive }"></div>  ✅
```

### Angular DevTools

**Installation:**
- Extension: "Angular DevTools"

**Features:**
- Component tree
- Change detection profiling
- Injector tree
- Directive inspection

---

## CSS and Layout Issues

### Inspecting Elements

**Element Inspection Workflow:**
1. Right-click element → Inspect
2. View applied styles in Styles panel
3. Check computed values in Computed panel
4. Modify CSS live to test fixes
5. Check box model dimensions

### Common CSS Issues

**1. Element Not Visible**
```css
/* Check for: */
display: none;
visibility: hidden;
opacity: 0;
width: 0; height: 0;
position: absolute; left: -9999px;
z-index: -1;
```

**2. Overlapping Elements**
```css
/* Debug with: */
* {
    outline: 1px solid red;  /* See all element boxes */
}

/* Fix with: */
position: relative;
z-index: 10;  /* Bring to front */
```

**3. Flexbox Issues**
```css
/* Debug container */
.container {
    display: flex;
    flex-direction: row;  /* Check direction */
    justify-content: space-between;  /* Main axis */
    align-items: center;  /* Cross axis */
    border: 1px solid red;  /* Visualize */
}

/* Debug items */
.item {
    flex: 1;  /* Grow to fill */
    min-width: 0;  /* Prevent overflow */
    border: 1px solid blue;
}
```

**4. Grid Layout Issues**
```css
/* Debug grid */
.grid-container {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
    
    /* Visualize in DevTools: */
    /* Chrome: Toggle grid overlay */
    /* Firefox: Grid inspector */
}
```

**5. Positioning Problems**
```css
/* Understanding positions */
position: static;    /* Default, normal flow */
position: relative;  /* Relative to normal position */
position: absolute;  /* Relative to positioned ancestor */
position: fixed;     /* Relative to viewport */
position: sticky;    /* Hybrid relative/fixed */
```

### Box Model Debugging

```
┌─────────────────────────────┐
│         Margin              │
│  ┌─────────────────────┐    │
│  │      Border         │    │
│  │  ┌──────────────┐   │    │
│  │  │   Padding    │   │    │
│  │  │  ┌────────┐  │   │    │
│  │  │  │Content │  │   │    │
│  │  │  └────────┘  │   │    │
│  │  └──────────────┘   │    │
│  └─────────────────────┘    │
└─────────────────────────────┘
```

**Check box model in DevTools:**
- Select element
- View box model diagram
- See exact pixel values
- Identify spacing issues

### CSS Specificity

```css
/* Specificity weight: */
!important:     ∞
inline styles:  1000
#id:           100
.class:        10
element:       1

/* Example: */
div.class#id { }  /* 100 + 10 + 1 = 111 */
.class.class { }  /* 10 + 10 = 20 */
div div { }       /* 1 + 1 = 2 */
```

---

## JavaScript Errors

### Using Breakpoints

**Types of Breakpoints:**

**1. Line Breakpoints**
```javascript
function calculateTotal(items) {
    let total = 0;  // Set breakpoint here
    for (const item of items) {
        total += item.price;
    }
    return total;
}
```

**2. Conditional Breakpoints**
```javascript
// Right-click breakpoint → Edit breakpoint
// Condition: item.price > 100
for (const item of items) {
    total += item.price;  // Pauses only when price > 100
}
```

**3. Logpoints (No pause)**
```javascript
// Right-click line → Add logpoint
// Expression: 'Price:', item.price
```

**4. Event Listener Breakpoints**
- DevTools → Sources → Event Listener Breakpoints
- Check "click", "submit", etc.
- Code pauses when event fires

**5. XHR/Fetch Breakpoints**
- DevTools → Sources → XHR/Fetch Breakpoints
- Add URL pattern
- Pauses when request matches

### Debugger Statement

```javascript
function problematicFunction() {
    debugger;  // Execution pauses here if DevTools open
    const result = calculation();
    return result;
}
```

### Call Stack Analysis

```
Error: Cannot read property 'name' of undefined
    at getUserName (app.js:45)
    at displayUser (app.js:23)
    at handleClick (app.js:12)
    at HTMLButtonElement.<anonymous>

Analysis:
1. Error occurred in getUserName at line 45
2. Called from displayUser at line 23
3. Which was called from handleClick at line 12
4. Triggered by button click
```

### Common JavaScript Errors

**1. TypeError: Cannot read property 'X' of undefined**
```javascript
// Problem
const user = undefined;
console.log(user.name);  // ❌ TypeError

// Solutions
// Optional chaining
console.log(user?.name);  // ✅ undefined (no error)

// Nullish coalescing
const name = user?.name ?? 'Guest';  // ✅ 'Guest'

// Guard clause
if (user) {
    console.log(user.name);  // ✅
}
```

**2. ReferenceError: X is not defined**
```javascript
// Problem: Variable doesn't exist
console.log(unknownVariable);  // ❌ ReferenceError

// Check:
// - Variable spelling
// - Variable scope
// - Import statements
```

**3. SyntaxError: Unexpected token**
```javascript
// Problem: Syntax error
const data = { name: 'John' age: 30 };  // ❌ Missing comma

// Solution
const data = { name: 'John', age: 30 };  // ✅
```

**4. Promise rejection unhandled**
```javascript
// Problem: No error handling
fetch('/api/data')
    .then(res => res.json())
    .then(data => console.log(data));  // ❌ No catch

// Solution
fetch('/api/data')
    .then(res => res.json())
    .then(data => console.log(data))
    .catch(err => console.error('Error:', err));  // ✅
```

---

## Performance Issues

### Performance Profiling

**Chrome Performance Tab:**
1. Open DevTools → Performance
2. Click Record
3. Perform actions
4. Stop recording
5. Analyze timeline

**Key Metrics:**
- **FPS**: Frames per second (aim for 60)
- **CPU**: JavaScript execution time
- **Network**: Request timing
- **Screenshots**: Visual timeline

### JavaScript Performance

**Slow Code Patterns:**

```javascript
// ❌ BAD: DOM manipulation in loop
for (let i = 0; i < 1000; i++) {
    document.body.appendChild(createDiv(i));
}

// ✅ GOOD: Batch DOM updates
const fragment = document.createDocumentFragment();
for (let i = 0; i < 1000; i++) {
    fragment.appendChild(createDiv(i));
}
document.body.appendChild(fragment);
```

```javascript
// ❌ BAD: Unnecessary re-renders
function Component({ items }) {
    // Creates new function every render
    const handleClick = () => { /* ... */ };
    
    return items.map(item => (
        <Item key={item.id} onClick={handleClick} />
    ));
}

// ✅ GOOD: Memoize callbacks
function Component({ items }) {
    const handleClick = useCallback(() => { /* ... */ }, []);
    
    return items.map(item => (
        <Item key={item.id} onClick={handleClick} />
    ));
}
```

### Memory Leaks

**Common Causes:**
1. **Event listeners not removed**
2. **Timers not cleared**
3. **Global variables holding references**
4. **Closures retaining references**

**Detection:**
1. Take heap snapshot
2. Perform action
3. Take another snapshot
4. Compare snapshots
5. Investigate growing objects

---

## Mobile and Responsive Debugging

### Device Emulation

**Chrome DevTools:**
1. Toggle device toolbar (`Ctrl+Shift+M`)
2. Select device preset
3. Test responsive behavior
4. Test touch events

**Testing Different Viewports:**
```css
/* Use media queries */
@media (max-width: 768px) {
    .container {
        flex-direction: column;
    }
}

/* Test in DevTools */
/* Device toolbar → Responsive → Enter width */
```

### Remote Debugging

**Android + Chrome:**
1. Enable USB debugging on phone
2. Connect phone to computer
3. Open `chrome://inspect` in Chrome
4. Select device and page
5. Inspect and debug

**iOS + Safari:**
1. Enable Web Inspector on iPhone
2. Connect to Mac
3. Safari → Develop → [Device] → [Page]
4. Inspect and debug

### Touch Event Debugging

```javascript
// Log touch events
element.addEventListener('touchstart', (e) => {
    console.log('Touch started:', e.touches);
});

element.addEventListener('touchmove', (e) => {
    console.log('Touch moved:', e.touches);
});

element.addEventListener('touchend', (e) => {
    console.log('Touch ended');
});
```

---

## Common Frontend Bugs

### 1. Race Conditions

```javascript
// Problem: Race condition
let data = null;
fetchData().then(result => data = result);
console.log(data);  // ❌ null (fetch not complete)

// Solution: Wait for promise
const data = await fetchData();
console.log(data);  // ✅ Correct data
```

### 2. Stale Closures

```javascript
// Problem: Stale closure
function Counter() {
    const [count, setCount] = useState(0);
    
    useEffect(() => {
        const interval = setInterval(() => {
            console.log(count);  // ❌ Always 0
            setCount(count + 1);  // ❌ Updates to 1 repeatedly
        }, 1000);
        return () => clearInterval(interval);
    }, []);  // Empty deps = stale closure
}

// Solution: Use functional update
useEffect(() => {
    const interval = setInterval(() => {
        setCount(c => c + 1);  // ✅ Always gets latest
    }, 1000);
    return () => clearInterval(interval);
}, []);
```

### 3. Memory Leaks

```javascript
// Problem: Event listener leak
useEffect(() => {
    window.addEventListener('resize', handleResize);
    // ❌ Listener never removed
});

// Solution: Cleanup
useEffect(() => {
    window.addEventListener('resize', handleResize);
    return () => {
        window.removeEventListener('resize', handleResize);  // ✅
    };
}, []);
```

### 4. Asynchronous State Updates

```javascript
// Problem: Assuming immediate update
setState(newValue);
console.log(state);  // ❌ Still old value

// Solution: Use callback or effect
setState(newValue);
// Wait for next render to use new value
useEffect(() => {
    console.log(state);  // ✅ New value
}, [state]);
```

---

## Summary

**Frontend Debugging Toolkit:**

✅ **Browser DevTools**
- Master all tabs (Elements, Console, Network, etc.)
- Use breakpoints effectively
- Profile performance regularly

✅ **Console Techniques**
- Strategic logging
- Proper error handling
- Performance timing

✅ **Network Debugging**
- Monitor all requests
- Check CORS issues
- Verify response data

✅ **Framework DevTools**
- React/Vue/Angular specific tools
- Component inspection
- State management debugging

✅ **CSS Debugging**
- Box model understanding
- Specificity rules
- Layout visualization

**Remember**: The browser DevTools are incredibly powerful. Invest time learning them thoroughly - they'll save you hours of debugging time.
