# Common Debugging Patterns and Solutions

## Table of Contents
1. [Null/Undefined Errors](#nullundefined-errors)
2. [Async/Promise Issues](#asyncpromise-issues)
3. [State Management Problems](#state-management-problems)
4. [API Integration Issues](#api-integration-issues)
5. [Performance Problems](#performance-problems)
6. [Database Query Issues](#database-query-issues)
7. [Authentication/Authorization](#authenticationauthorization)
8. [Caching Problems](#caching-problems)
9. [Race Conditions](#race-conditions)
10. [Memory Leaks](#memory-leaks)

---

## Null/Undefined Errors

### Pattern
```
TypeError: Cannot read property 'x' of undefined
TypeError: Cannot read property 'x' of null
NullPointerException
```

### Common Causes
- Variable not initialized
- API returns null/undefined
- Destructuring optional properties
- Accessing nested properties without checking parent

### Solutions

**JavaScript:**
```javascript
// ❌ BAD
const name = user.profile.name;

// ✅ GOOD - Optional chaining
const name = user?.profile?.name;

// ✅ GOOD - Nullish coalescing
const name = user?.profile?.name ?? 'Unknown';

// ✅ GOOD - Default values in destructuring
const { name = 'Unknown' } = user?.profile || {};
```

**Python:**
```python
# ❌ BAD
result = data['user']['email']

# ✅ GOOD
result = data.get('user', {}).get('email')

# ✅ GOOD - With default
result = data.get('user', {}).get('email', 'no-email')
```

---

## Async/Promise Issues

### Pattern
- Functions complete in wrong order
- "Promise pending" instead of actual value
- Race conditions with async operations
- Unhandled promise rejections

### Common Causes
- Missing await keyword
- Not returning promises from .then()
- Mixing async/await with callbacks
- Not handling promise rejections

### Solutions

**JavaScript:**
```javascript
// ❌ BAD - Missing await
async function fetchUser() {
  const user = getUserAPI();  // Returns promise, not user!
  console.log(user.name);  // undefined or error
}

// ✅ GOOD
async function fetchUser() {
  const user = await getUserAPI();
  console.log(user.name);
}

// ❌ BAD - Not returning promise
getData()
  .then(data => processData(data))  // Doesn't return!
  .then(result => console.log(result));  // result is undefined

// ✅ GOOD
getData()
  .then(data => {
    return processData(data);  // Return the promise
  })
  .then(result => console.log(result));

// ❌ BAD - Unhandled rejection
async function riskyOperation() {
  await mightFail();  // If this throws, app crashes
}

// ✅ GOOD
async function riskyOperation() {
  try {
    await mightFail();
  } catch (error) {
    console.error('Operation failed:', error);
    // Handle or rethrow
  }
}
```

**Python:**
```python
# ❌ BAD - Mixing sync and async
async def process():
    data = fetch_data()  # If this is async, it won't work
    return data

# ✅ GOOD
async def process():
    data = await fetch_data()
    return data
```

---

## State Management Problems

### Pattern
- UI not updating when data changes
- Stale data displayed
- State updates not reflecting
- Infinite render loops

### Common Causes (React/Vue)
- Mutating state directly
- Not using immutable updates
- Missing dependencies in hooks
- Closure capturing old state

### Solutions

**React:**
```javascript
// ❌ BAD - Mutating state
const addItem = () => {
  items.push(newItem);  // Direct mutation!
  setItems(items);  // React won't detect change
};

// ✅ GOOD - Immutable update
const addItem = () => {
  setItems([...items, newItem]);
};

// ❌ BAD - Missing dependency
useEffect(() => {
  fetchData(userId);  // userId not in dependencies!
}, []);

// ✅ GOOD
useEffect(() => {
  fetchData(userId);
}, [userId]);

// ❌ BAD - Closure problem
const incrementCounter = () => {
  setTimeout(() => {
    setCount(count + 1);  // Uses stale count value!
  }, 1000);
};

// ✅ GOOD - Functional update
const incrementCounter = () => {
  setTimeout(() => {
    setCount(prevCount => prevCount + 1);
  }, 1000);
};
```

---

## API Integration Issues

### Pattern
- CORS errors
- 401/403 errors
- Timeout errors
- Unexpected response format

### Solutions

**CORS Issues:**
```javascript
// Server-side fix (Express.js)
const cors = require('cors');
app.use(cors({
  origin: 'https://your-frontend.com',
  credentials: true
}));
```

**Authentication:**
```javascript
// ❌ BAD - No error handling
const response = await fetch('/api/data', {
  headers: { 'Authorization': `Bearer ${token}` }
});
const data = await response.json();

// ✅ GOOD
const response = await fetch('/api/data', {
  headers: { 'Authorization': `Bearer ${token}` }
});

if (!response.ok) {
  if (response.status === 401) {
    // Token expired, refresh or redirect to login
    await refreshToken();
    return retry();
  }
  throw new Error(`API error: ${response.status}`);
}

const data = await response.json();
```

**Timeout Handling:**
```javascript
// ✅ GOOD - With timeout
const fetchWithTimeout = (url, timeout = 5000) => {
  return Promise.race([
    fetch(url),
    new Promise((_, reject) =>
      setTimeout(() => reject(new Error('Timeout')), timeout)
    )
  ]);
};
```

---

## Performance Problems

### Pattern
- Slow page loads
- UI freezes
- High memory usage
- Sluggish interactions

### Solutions

**Debouncing/Throttling:**
```javascript
// ❌ BAD - Fires on every keystroke
<input onChange={e => searchAPI(e.target.value)} />

// ✅ GOOD - Debounced
import { debounce } from 'lodash';

const debouncedSearch = debounce(searchAPI, 300);
<input onChange={e => debouncedSearch(e.target.value)} />
```

**Lazy Loading:**
```javascript
// ✅ GOOD - Code splitting
const HeavyComponent = lazy(() => import('./HeavyComponent'));

<Suspense fallback={<Loading />}>
  <HeavyComponent />
</Suspense>
```

**Memoization:**
```javascript
// ❌ BAD - Recalculates on every render
const expensiveValue = calculateExpensiveValue(data);

// ✅ GOOD - Memoized
const expensiveValue = useMemo(
  () => calculateExpensiveValue(data),
  [data]
);
```

---

## Database Query Issues

### Pattern
- Slow queries
- N+1 query problem
- Query timeouts
- Incorrect results

### Solutions

**N+1 Problem:**
```python
# ❌ BAD - N+1 queries
users = User.query.all()
for user in users:
    posts = user.posts  # Separate query for each user!

# ✅ GOOD - Eager loading
users = User.query.options(joinedload(User.posts)).all()
```

**Query Optimization:**
```sql
-- ❌ BAD - Full table scan
SELECT * FROM orders WHERE customer_name = 'John';

-- ✅ GOOD - Use indexed column
-- First, create index:
CREATE INDEX idx_customer_name ON orders(customer_name);

-- Then query uses index automatically
SELECT * FROM orders WHERE customer_name = 'John';

-- ❌ BAD - Select all columns
SELECT * FROM orders WHERE id = 123;

-- ✅ GOOD - Select only needed columns
SELECT id, total, status FROM orders WHERE id = 123;
```

---

## Authentication/Authorization

### Pattern
- Token expired errors
- Permission denied
- Session issues
- CSRF errors

### Solutions

**Token Refresh:**
```javascript
// ✅ GOOD - Automatic token refresh
const apiCall = async (url) => {
  let response = await fetch(url, {
    headers: { 'Authorization': `Bearer ${getToken()}` }
  });
  
  if (response.status === 401) {
    // Try to refresh token
    await refreshAuthToken();
    // Retry with new token
    response = await fetch(url, {
      headers: { 'Authorization': `Bearer ${getToken()}` }
    });
  }
  
  return response;
};
```

---

## Common Anti-Patterns

### 1. Swallowing Errors
```javascript
// ❌ BAD
try {
  riskyOperation();
} catch (e) {
  // Silent failure - very bad!
}

// ✅ GOOD
try {
  riskyOperation();
} catch (e) {
  console.error('Operation failed:', e);
  notifyUser('Something went wrong');
  logToMonitoring(e);
}
```

### 2. Using Console.log for Debugging
```javascript
// ❌ BAD - console.log everywhere
console.log('user:', user);
console.log('here 1');
console.log('data:', data);

// ✅ GOOD - Use proper logging with levels
logger.debug('User data loaded', { userId: user.id });
logger.info('Processing started');
logger.error('Failed to process', { error, data });
```

### 3. Not Validating Input
```javascript
// ❌ BAD
function divide(a, b) {
  return a / b;  // What if b is 0?
}

// ✅ GOOD
function divide(a, b) {
  if (b === 0) {
    throw new Error('Division by zero');
  }
  return a / b;
}
```

---

## Quick Debugging Checklist

When encountering a bug:

- [ ] Can you reproduce it consistently?
- [ ] Have you checked the browser console/terminal for errors?
- [ ] Have you reviewed recent code changes?
- [ ] Have you checked network requests (if applicable)?
- [ ] Have you verified input data is in expected format?
- [ ] Have you added logging at key points?
- [ ] Have you checked for null/undefined values?
- [ ] Have you tested edge cases?
- [ ] Have you verified all async operations are awaited?
- [ ] Have you checked for typos in variable/function names?

---

For more debugging techniques, see:
- ERROR_CODES.md for HTTP status codes
- PERFORMANCE_GUIDE.md for optimization strategies
- DATABASE_DEBUGGING.md for SQL-specific issues
