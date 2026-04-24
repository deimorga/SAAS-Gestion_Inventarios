# Complete Error Code Reference

## HTTP Status Codes

### 1xx Informational
- **100 Continue**: Client should continue request
- **101 Switching Protocols**: Server switching protocols per client request

### 2xx Success
- **200 OK**: Request succeeded
- **201 Created**: Resource created successfully
- **202 Accepted**: Request accepted for processing
- **204 No Content**: Success but no content to return
- **206 Partial Content**: Partial GET request successful

### 3xx Redirection
- **301 Moved Permanently**: Resource permanently moved
- **302 Found**: Temporary redirect
- **304 Not Modified**: Use cached version
- **307 Temporary Redirect**: Temporary redirect (method preserved)
- **308 Permanent Redirect**: Permanent redirect (method preserved)

### 4xx Client Errors

#### 400 Bad Request
**Meaning**: Request syntax is invalid

**Common Causes**:
- Malformed JSON
- Missing required fields
- Invalid data types
- Encoding issues

**How to Debug**:
```javascript
// Check request body
console.log('Sending:', JSON.stringify(requestBody, null, 2));

// Validate before sending
if (!requestBody.userId) {
  throw new Error('userId is required');
}

// Check content-type header
headers: {
  'Content-Type': 'application/json'
}
```

#### 401 Unauthorized
**Meaning**: Authentication required or failed

**Common Causes**:
- Missing authentication token
- Expired token
- Invalid credentials
- Token not in correct format

**How to Debug**:
```javascript
// Check if token exists
console.log('Token:', localStorage.getItem('authToken'));

// Verify token format
const token = 'Bearer ' + actualToken;  // Many APIs need 'Bearer ' prefix

// Check token expiration
const decoded = jwtDecode(token);
if (decoded.exp * 1000 < Date.now()) {
  console.log('Token expired');
  // Refresh token
}
```

#### 403 Forbidden
**Meaning**: Authenticated but not authorized

**Common Causes**:
- Insufficient permissions
- Resource owner mismatch
- Account suspended/disabled
- IP whitelist restriction

**How to Debug**:
- Check user role/permissions in database
- Verify resource ownership
- Check server-side authorization logic
- Review IP restrictions

#### 404 Not Found
**Meaning**: Resource doesn't exist

**Common Causes**:
- Wrong URL/endpoint
- Resource was deleted
- Typo in route
- Route not registered

**How to Debug**:
```javascript
// Log the exact URL being called
console.log('Calling:', url);

// Check if ID exists
const user = await User.findById(userId);
if (!user) {
  throw new NotFoundError('User not found');
}

// Verify route registration (Express)
app.get('/api/users/:id', handler);  // Make sure this exists
```

#### 409 Conflict
**Meaning**: Request conflicts with current state

**Common Causes**:
- Duplicate key (email, username)
- Version mismatch (optimistic locking)
- Business rule violation
- Resource already exists

**How to Debug**:
```python
# Check for duplicates
existing = User.query.filter_by(email=email).first()
if existing:
    raise ConflictError('Email already registered')

# Check version
if resource.version != expected_version:
    raise ConflictError('Resource was modified')
```

#### 422 Unprocessable Entity
**Meaning**: Request valid but semantically incorrect

**Common Causes**:
- Validation errors
- Business logic violation
- Invalid data relationships
- Constraint violation

**How to Debug**:
- Check validation rules
- Review error response body for details
- Verify data relationships
- Check required fields

#### 429 Too Many Requests
**Meaning**: Rate limit exceeded

**Common Causes**:
- Too many requests too quickly
- No rate limit handling
- Loop making repeated requests

**How to Debug**:
```javascript
// Implement exponential backoff
async function retryWithBackoff(fn, maxRetries = 3) {
  for (let i = 0; i < maxRetries; i++) {
    try {
      return await fn();
    } catch (error) {
      if (error.status === 429) {
        const delay = Math.pow(2, i) * 1000;  // 1s, 2s, 4s
        console.log(`Rate limited, retrying in ${delay}ms`);
        await sleep(delay);
      } else {
        throw error;
      }
    }
  }
  throw new Error('Max retries exceeded');
}
```

### 5xx Server Errors

#### 500 Internal Server Error
**Meaning**: Unhandled server error

**Common Causes**:
- Unhandled exception
- Logic error in code
- Configuration error
- Missing dependency

**How to Debug**:
1. Check server logs immediately
2. Look for stack trace
3. Review recent code changes
4. Add try-catch blocks
5. Check error monitoring (Sentry, etc.)

#### 502 Bad Gateway
**Meaning**: Upstream server sent invalid response

**Common Causes**:
- Backend service down
- Network issue
- Load balancer misconfigured
- Timeout from upstream

**How to Debug**:
- Check if backend service is running
- Verify network connectivity
- Check load balancer configuration
- Review upstream service logs

#### 503 Service Unavailable
**Meaning**: Service temporarily unavailable

**Common Causes**:
- Maintenance mode
- Overloaded server
- Database connection pool exhausted
- Dependency down

**How to Debug**:
- Check service status
- Monitor resource usage (CPU, memory)
- Review health check endpoint
- Check dependency services

#### 504 Gateway Timeout
**Meaning**: Upstream server didn't respond in time

**Common Causes**:
- Slow database query
- External API timeout
- Resource-intensive operation
- Network latency

**How to Debug**:
```javascript
// Add timeout to requests
const timeout = 5000;  // 5 seconds
const controller = new AbortController();
const timeoutId = setTimeout(() => controller.abort(), timeout);

try {
  const response = await fetch(url, { signal: controller.signal });
  clearTimeout(timeoutId);
  return response;
} catch (error) {
  if (error.name === 'AbortError') {
    console.error('Request timed out');
  }
  throw error;
}
```

---

## Database Error Codes

### PostgreSQL

- **23505**: Unique violation (duplicate key)
- **23503**: Foreign key violation
- **23502**: NOT NULL constraint violation
- **42P01**: Undefined table
- **42703**: Undefined column
- **22P02**: Invalid text representation (type mismatch)

### MySQL/MariaDB

- **1062**: Duplicate entry (unique constraint)
- **1452**: Foreign key constraint fails
- **1048**: Column cannot be null
- **1146**: Table doesn't exist
- **1054**: Unknown column

### MongoDB

- **11000**: Duplicate key error
- **121**: Document validation failed
- **2**: Bad value (type mismatch)

---

## Common Application Error Patterns

### Network Errors

```javascript
// ECONNREFUSED - Connection refused
// Cause: Server not running or port wrong
// Fix: Start server, verify port number

// ETIMEDOUT - Connection timeout
// Cause: Server not responding, firewall, network issue
// Fix: Check server status, network connectivity

// ENOTFOUND - DNS lookup failed
// Cause: Invalid hostname, DNS issues
// Fix: Verify hostname, check DNS settings

// ECONNRESET - Connection reset
// Cause: Server closed connection unexpectedly
// Fix: Check server logs, add error handling
```

### File System Errors

```javascript
// ENOENT - No such file or directory
// Cause: File doesn't exist, wrong path
// Fix: Verify file path, create file if needed

// EACCES - Permission denied
// Cause: Insufficient permissions
// Fix: Check file permissions, run with appropriate privileges

// EISDIR - Is a directory
// Cause: Trying to read directory as file
// Fix: Check if path is file or directory before operation

// EEXIST - File already exists
// Cause: Trying to create existing file
// Fix: Check if file exists before creation, or use flags to overwrite
```

---

## Exit Codes

### Unix/Linux Exit Codes

- **0**: Success
- **1**: General error
- **2**: Misuse of shell command
- **126**: Command cannot execute
- **127**: Command not found
- **130**: Script terminated by Ctrl+C
- **137**: Process killed (SIGKILL)
- **143**: Process terminated (SIGTERM)

### Application-Specific

```javascript
// Define meaningful exit codes
const EXIT_CODES = {
  SUCCESS: 0,
  CONFIG_ERROR: 1,
  CONNECTION_ERROR: 2,
  VALIDATION_ERROR: 3,
  TIMEOUT: 4
};

// Use them
if (!config.isValid()) {
  console.error('Invalid configuration');
  process.exit(EXIT_CODES.CONFIG_ERROR);
}
```

---

## Error Handling Best Practices

### 1. Always Handle Errors

```javascript
// ❌ BAD
await riskyOperation();

// ✅ GOOD
try {
  await riskyOperation();
} catch (error) {
  console.error('Operation failed:', error);
  // Handle appropriately
}
```

### 2. Provide Context

```javascript
// ❌ BAD
throw new Error('Failed');

// ✅ GOOD
throw new Error(`Failed to update user ${userId}: ${error.message}`);
```

### 3. Use Specific Error Types

```javascript
// ✅ GOOD
class ValidationError extends Error {
  constructor(field, message) {
    super(message);
    this.name = 'ValidationError';
    this.field = field;
    this.statusCode = 422;
  }
}

class NotFoundError extends Error {
  constructor(resource, id) {
    super(`${resource} ${id} not found`);
    this.name = 'NotFoundError';
    this.statusCode = 404;
  }
}
```

### 4. Log Errors Properly

```javascript
// ✅ GOOD
logger.error('Database query failed', {
  error: error.message,
  stack: error.stack,
  query: sqlQuery,
  params: queryParams,
  userId: req.user?.id
});
```

---

## Quick Reference Table

| Code | Name | Category | Action |
|------|------|----------|--------|
| 400 | Bad Request | Client | Fix request format |
| 401 | Unauthorized | Client | Check authentication |
| 403 | Forbidden | Client | Check permissions |
| 404 | Not Found | Client | Verify resource/URL |
| 409 | Conflict | Client | Check for duplicates |
| 422 | Unprocessable | Client | Validate input data |
| 429 | Rate Limit | Client | Implement backoff |
| 500 | Server Error | Server | Check server logs |
| 502 | Bad Gateway | Server | Check upstream |
| 503 | Unavailable | Server | Check service status |
| 504 | Timeout | Server | Optimize or increase timeout |

---

For debugging strategies, see DEBUGGING_PATTERNS.md
For performance issues, see PERFORMANCE_GUIDE.md
