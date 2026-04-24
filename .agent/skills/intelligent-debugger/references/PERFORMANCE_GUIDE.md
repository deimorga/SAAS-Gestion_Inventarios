# Performance Debugging Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Performance Profiling Basics](#performance-profiling-basics)
3. [Identifying Bottlenecks](#identifying-bottlenecks)
4. [Memory Performance](#memory-performance)
5. [CPU Performance](#cpu-performance)
6. [Network Performance](#network-performance)
7. [Database Performance](#database-performance)
8. [Frontend Performance](#frontend-performance)
9. [Performance Tools](#performance-tools)
10. [Optimization Strategies](#optimization-strategies)

---

## Introduction

Performance debugging focuses on identifying and resolving bottlenecks that slow down your application. Unlike functional bugs, performance issues often manifest as gradual degradation or spikes under specific conditions.

**Key Performance Metrics:**
- **Response Time**: How long operations take
- **Throughput**: Number of operations per second
- **Resource Usage**: CPU, memory, network, disk I/O
- **Latency**: Delay before operation starts
- **Scalability**: Performance under increased load

---

## Performance Profiling Basics

### Profiling Methodology

1. **Establish Baseline**
   - Measure current performance
   - Document normal operating conditions
   - Identify performance goals

2. **Isolate Problem Areas**
   - Use profilers to identify hot spots
   - Focus on code that runs frequently
   - Look for operations in loops

3. **Measure Impact**
   - Benchmark before optimization
   - Measure after each change
   - Compare results objectively

### Types of Profiling

**CPU Profiling**
- Identifies code consuming most CPU time
- Shows function call frequencies
- Reveals computational bottlenecks

**Memory Profiling**
- Tracks memory allocation
- Identifies memory leaks
- Shows object retention patterns

**I/O Profiling**
- Measures disk read/write operations
- Tracks network requests
- Identifies I/O bottlenecks

---

## Identifying Bottlenecks

### Common Performance Bottlenecks

1. **N+1 Query Problem**
   ```python
   # BAD: Makes N+1 database queries
   users = User.query.all()
   for user in users:
       orders = user.orders.all()  # Query per user!
   
   # GOOD: Single query with join
   users = User.query.options(joinedload(User.orders)).all()
   ```

2. **Unoptimized Loops**
   ```python
   # BAD: O(n²) complexity
   def find_duplicates(items):
       duplicates = []
       for i in range(len(items)):
           for j in range(i+1, len(items)):
               if items[i] == items[j]:
                   duplicates.append(items[i])
       return duplicates
   
   # GOOD: O(n) with set
   def find_duplicates(items):
       seen = set()
       duplicates = set()
       for item in items:
           if item in seen:
               duplicates.add(item)
           seen.add(item)
       return list(duplicates)
   ```

3. **Blocking Operations**
   - Synchronous I/O in async contexts
   - Holding locks too long
   - Waiting for external services

4. **Resource Leaks**
   - Unclosed file handles
   - Database connections not released
   - Event listeners not removed

### Bottleneck Detection Strategy

```
1. Profile application under realistic load
2. Identify functions with highest:
   - Total time (cumulative)
   - Self time (excluding called functions)
   - Call count
3. Focus on high-impact areas first
4. Use 80/20 rule: 20% of code causes 80% of performance issues
```

---

## Memory Performance

### Memory Leak Detection

**Symptoms:**
- Gradually increasing memory usage
- Out of memory errors
- Application slowdown over time

**Detection Methods:**

**Python Memory Profiling:**
```python
import tracemalloc
import gc

# Start tracking
tracemalloc.start()

# Your code here
result = expensive_operation()

# Get memory usage
current, peak = tracemalloc.get_traced_memory()
print(f"Current: {current / 1024 / 1024:.2f} MB")
print(f"Peak: {peak / 1024 / 1024:.2f} MB")

# Get top memory consumers
snapshot = tracemalloc.take_snapshot()
top_stats = snapshot.statistics('lineno')

for stat in top_stats[:10]:
    print(stat)

tracemalloc.stop()
```

**JavaScript Memory Profiling:**
```javascript
// Take heap snapshot in Chrome DevTools
// 1. Open DevTools → Memory tab
// 2. Select "Heap snapshot"
// 3. Take snapshot before/after operation
// 4. Compare snapshots to find leaks

// Programmatic memory check
if (performance.memory) {
    console.log({
        used: `${(performance.memory.usedJSHeapSize / 1048576).toFixed(2)} MB`,
        total: `${(performance.memory.totalJSHeapSize / 1048576).toFixed(2)} MB`,
        limit: `${(performance.memory.jsHeapSizeLimit / 1048576).toFixed(2)} MB`
    });
}
```

### Common Memory Issues

**1. Caching Gone Wrong**
```python
# BAD: Unbounded cache grows forever
cache = {}
def get_user(user_id):
    if user_id not in cache:
        cache[user_id] = fetch_from_db(user_id)
    return cache[user_id]

# GOOD: Use LRU cache with size limit
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_user(user_id):
    return fetch_from_db(user_id)
```

**2. Event Listener Leaks**
```javascript
// BAD: Listener never removed
function setupComponent() {
    document.addEventListener('click', handleClick);
}

// GOOD: Clean up listeners
function setupComponent() {
    const handleClick = () => { /* ... */ };
    document.addEventListener('click', handleClick);
    
    return () => {
        document.removeEventListener('click', handleClick);
    };
}
```

---

## CPU Performance

### CPU Profiling Tools

**Python - cProfile:**
```python
import cProfile
import pstats

# Profile function
profiler = cProfile.Profile()
profiler.enable()

expensive_function()

profiler.disable()

# Print statistics
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 functions
```

**Node.js - Built-in Profiler:**
```bash
# Generate CPU profile
node --prof app.js

# Process profile
node --prof-process isolate-*.log > profile.txt
```

### Optimization Techniques

**1. Algorithm Optimization**
```python
# O(n²) - Slow
def find_pairs_sum(arr, target):
    pairs = []
    for i in range(len(arr)):
        for j in range(i+1, len(arr)):
            if arr[i] + arr[j] == target:
                pairs.append((arr[i], arr[j]))
    return pairs

# O(n) - Fast
def find_pairs_sum(arr, target):
    seen = set()
    pairs = []
    for num in arr:
        complement = target - num
        if complement in seen:
            pairs.append((complement, num))
        seen.add(num)
    return pairs
```

**2. Avoid Repeated Computations**
```python
# BAD: Recomputes each iteration
for i in range(len(items)):
    expensive_calculation = complex_function()
    items[i] = items[i] * expensive_calculation

# GOOD: Compute once
expensive_calculation = complex_function()
for i in range(len(items)):
    items[i] = items[i] * expensive_calculation
```

**3. Use Built-in Functions**
```python
# SLOW: Manual implementation
def sum_list(numbers):
    total = 0
    for num in numbers:
        total += num
    return total

# FAST: Built-in function (C implementation)
total = sum(numbers)
```

---

## Network Performance

### Network Request Optimization

**1. Batch Requests**
```javascript
// BAD: Multiple sequential requests
async function getUsersData(userIds) {
    const users = [];
    for (const id of userIds) {
        const user = await fetch(`/api/users/${id}`);
        users.push(await user.json());
    }
    return users;
}

// GOOD: Single batch request
async function getUsersData(userIds) {
    const response = await fetch('/api/users/batch', {
        method: 'POST',
        body: JSON.stringify({ ids: userIds })
    });
    return response.json();
}
```

**2. Request Caching**
```javascript
// Simple cache implementation
const cache = new Map();

async function fetchWithCache(url, ttl = 60000) {
    const cached = cache.get(url);
    if (cached && Date.now() - cached.timestamp < ttl) {
        return cached.data;
    }
    
    const response = await fetch(url);
    const data = await response.json();
    
    cache.set(url, {
        data,
        timestamp: Date.now()
    });
    
    return data;
}
```

**3. Connection Pooling**
```python
# Use connection pooling for databases
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

engine = create_engine(
    'postgresql://user:pass@localhost/db',
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=0
)
```

### Latency Reduction

**1. CDN for Static Assets**
- Serve static files from CDN
- Reduce geographic latency
- Offload server bandwidth

**2. Compression**
```python
# Enable gzip compression
from flask import Flask
from flask_compress import Compress

app = Flask(__name__)
Compress(app)
```

**3. HTTP/2**
- Multiplexing multiple requests
- Server push capabilities
- Header compression

---

## Database Performance

### Query Optimization

**1. Use EXPLAIN to Analyze Queries**
```sql
-- See query execution plan
EXPLAIN ANALYZE
SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2025-01-01'
GROUP BY u.id, u.name
ORDER BY order_count DESC
LIMIT 10;
```

**2. Add Appropriate Indexes**
```sql
-- Identify missing indexes
-- Look for "Seq Scan" in EXPLAIN output

-- Add index for frequently queried columns
CREATE INDEX idx_users_created_at ON users(created_at);
CREATE INDEX idx_orders_user_id ON orders(user_id);

-- Compound index for multiple columns
CREATE INDEX idx_orders_user_status ON orders(user_id, status);
```

**3. Avoid SELECT ***
```sql
-- BAD: Fetches all columns
SELECT * FROM users WHERE id = 123;

-- GOOD: Only fetch needed columns
SELECT id, name, email FROM users WHERE id = 123;
```

### Connection Management

**1. Connection Pooling**
```python
# Configure connection pool
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://localhost/mydb',
    pool_size=10,          # Regular connections
    max_overflow=20,       # Additional connections when needed
    pool_timeout=30,       # Timeout waiting for connection
    pool_recycle=3600,     # Recycle connections after 1 hour
)
```

**2. Always Close Connections**
```python
# Use context managers
from contextlib import closing

with closing(connection.cursor()) as cursor:
    cursor.execute("SELECT * FROM users")
    results = cursor.fetchall()
# Connection automatically closed
```

---

## Frontend Performance

### Rendering Performance

**1. Virtual Scrolling for Long Lists**
```javascript
// Instead of rendering 10,000 items
<div>
  {items.map(item => <Item key={item.id} {...item} />)}
</div>

// Use virtual scrolling (react-window)
import { FixedSizeList } from 'react-window';

<FixedSizeList
  height={600}
  itemCount={items.length}
  itemSize={35}
  width="100%"
>
  {({ index, style }) => (
    <div style={style}>
      <Item {...items[index]} />
    </div>
  )}
</FixedSizeList>
```

**2. Code Splitting**
```javascript
// Lazy load components
import React, { lazy, Suspense } from 'react';

const HeavyComponent = lazy(() => import('./HeavyComponent'));

function App() {
    return (
        <Suspense fallback={<Loading />}>
            <HeavyComponent />
        </Suspense>
    );
}
```

**3. Debouncing/Throttling**
```javascript
// Debounce expensive operations
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

// Throttle scroll handlers
function throttle(func, limit) {
    let inThrottle;
    return function(...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}

// Usage
const handleSearch = debounce((query) => {
    fetchResults(query);
}, 300);

const handleScroll = throttle(() => {
    updateScrollPosition();
}, 100);
```

### Asset Optimization

**1. Image Optimization**
- Use WebP format
- Implement lazy loading
- Responsive images with srcset
- Compress images

**2. Minification**
- Minify JavaScript/CSS
- Remove console.logs
- Tree shaking unused code

**3. Bundle Size Reduction**
```bash
# Analyze bundle size
npm run build -- --stats
webpack-bundle-analyzer dist/stats.json

# Remove unused dependencies
npm prune
npx depcheck
```

---

## Performance Tools

### Profiling Tools

**Python:**
- `cProfile` - Built-in CPU profiler
- `memory_profiler` - Memory usage profiler
- `py-spy` - Sampling profiler (low overhead)
- `line_profiler` - Line-by-line profiling

**Node.js:**
- `clinic` - Performance profiling suite
- `0x` - Flamegraph profiler
- Chrome DevTools - Built-in profiler
- `autocannon` - HTTP load testing

**Browser:**
- Chrome DevTools Performance tab
- Lighthouse - Performance audits
- WebPageTest - Real-world testing
- React DevTools Profiler

### Monitoring Tools

- **APM Tools**: New Relic, Datadog, AppDynamics
- **Log Analysis**: Splunk, ELK Stack
- **Metrics**: Prometheus, Grafana
- **Tracing**: Jaeger, Zipkin

---

## Optimization Strategies

### Performance Optimization Workflow

1. **Measure First**
   - Never optimize without measurements
   - Establish performance baseline
   - Set clear performance goals

2. **Identify Bottlenecks**
   - Profile application under realistic load
   - Focus on high-impact areas
   - Use 80/20 rule

3. **Optimize**
   - Make one change at a time
   - Measure impact of each change
   - Keep successful optimizations

4. **Verify**
   - Ensure functionality still works
   - Check for regressions
   - Load test under various conditions

### Common Optimization Pitfalls

❌ **Premature Optimization**
- Don't optimize before profiling
- Focus on actual bottlenecks
- Measure to verify improvements

❌ **Micro-Optimizations**
- Don't optimize for milliseconds
- Focus on algorithmic improvements
- Consider maintainability

❌ **Over-Engineering**
- Keep it simple
- Add complexity only when needed
- Document performance-critical code

### Performance Best Practices

✅ **Use Caching Strategically**
- Cache expensive computations
- Set appropriate TTLs
- Invalidate cache when data changes

✅ **Asynchronous Operations**
- Don't block on I/O
- Use async/await or promises
- Parallelize independent operations

✅ **Database Optimization**
- Use indexes appropriately
- Optimize queries
- Use connection pooling

✅ **Frontend Optimization**
- Minimize bundle size
- Lazy load components
- Optimize images and assets

✅ **Monitor in Production**
- Track key metrics
- Set up alerts
- Regular performance reviews

---

## Summary

Performance debugging is about:
1. **Measuring** - Profile before optimizing
2. **Identifying** - Find real bottlenecks
3. **Optimizing** - Focus on high-impact areas
4. **Verifying** - Confirm improvements

**Key Takeaways:**
- Always profile before optimizing
- Fix bottlenecks, not assumptions
- Measure impact of each change
- Balance performance with maintainability
- Monitor performance in production

**Remember**: "Premature optimization is the root of all evil" - Donald Knuth
