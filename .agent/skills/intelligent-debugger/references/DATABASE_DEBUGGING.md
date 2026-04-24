# Database Debugging Guide

## Table of Contents
1. [Introduction](#introduction)
2. [Connection Issues](#connection-issues)
3. [Query Performance](#query-performance)
4. [Data Integrity Issues](#data-integrity-issues)
5. [Transaction Problems](#transaction-problems)
6. [Lock and Deadlock Issues](#lock-and-deadlock-issues)
7. [Replication and Sync Issues](#replication-and-sync-issues)
8. [Database-Specific Debugging](#database-specific-debugging)
9. [Monitoring and Tools](#monitoring-and-tools)

---

## Introduction

Database debugging requires understanding both your application logic and database internals. Common issues include slow queries, connection problems, data inconsistencies, and locking issues.

**Key Database Metrics:**
- Query execution time
- Connection pool usage
- Lock wait time
- Transaction throughput
- Cache hit ratio
- Disk I/O

---

## Connection Issues

### Symptoms
- "Connection refused" errors
- "Too many connections" errors
- Timeout when connecting
- Intermittent connection failures

### Debugging Steps

**1. Verify Database is Running**
```bash
# PostgreSQL
sudo systemctl status postgresql
ps aux | grep postgres

# MySQL
sudo systemctl status mysql
ps aux | grep mysqld

# MongoDB
sudo systemctl status mongod
ps aux | grep mongod
```

**2. Check Network Connectivity**
```bash
# Test connection to database host
ping database-host

# Check if database port is open
telnet database-host 5432  # PostgreSQL
telnet database-host 3306  # MySQL
telnet database-host 27017 # MongoDB

# Or use nc (netcat)
nc -zv database-host 5432
```

**3. Verify Credentials**
```python
# Test database connection
import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        database="mydb",
        user="myuser",
        password="mypass",
        connect_timeout=5
    )
    print("✅ Connection successful")
    conn.close()
except psycopg2.OperationalError as e:
    print(f"❌ Connection failed: {e}")
```

**4. Check Connection Limits**
```sql
-- PostgreSQL: Check current connections
SELECT count(*) as current_connections,
       (SELECT setting FROM pg_settings WHERE name = 'max_connections') as max_connections
FROM pg_stat_activity;

-- PostgreSQL: List all connections
SELECT pid, usename, application_name, client_addr, state, query
FROM pg_stat_activity;

-- MySQL: Check connections
SHOW STATUS LIKE 'Threads_connected';
SHOW STATUS LIKE 'Max_used_connections';
SHOW VARIABLES LIKE 'max_connections';

-- MySQL: List current connections
SHOW PROCESSLIST;
```

**5. Connection Pool Configuration**
```python
# SQLAlchemy connection pool settings
from sqlalchemy import create_engine

engine = create_engine(
    'postgresql://user:pass@localhost/db',
    pool_size=10,              # Regular connections in pool
    max_overflow=20,           # Additional connections when pool full
    pool_timeout=30,           # Seconds to wait for connection
    pool_recycle=3600,         # Recycle connections after 1 hour
    pool_pre_ping=True,        # Test connection before using
    echo_pool=True             # Log pool events
)
```

### Common Connection Issues

**Issue 1: Connection Pool Exhaustion**
```
Symptom: "QueuePool limit exceeded"
Solution:
1. Increase pool_size and max_overflow
2. Ensure connections are properly closed
3. Check for connection leaks in code
```

**Issue 2: Firewall Blocking**
```
Symptom: Connection timeout
Solution:
1. Check firewall rules
2. Verify security groups (cloud)
3. Confirm database listening on correct interface
```

**Issue 3: Authentication Failures**
```
Symptom: "password authentication failed"
Solution:
1. Verify username and password
2. Check pg_hba.conf (PostgreSQL)
3. Verify user permissions
4. Check SSL requirements
```

---

## Query Performance

### Identifying Slow Queries

**PostgreSQL - Enable Query Logging:**
```sql
-- In postgresql.conf
log_statement = 'all'
log_duration = on
log_min_duration_statement = 1000  -- Log queries > 1 second

-- Or set at runtime
ALTER DATABASE mydb SET log_min_duration_statement = 1000;
```

**MySQL - Slow Query Log:**
```sql
-- Enable slow query log
SET GLOBAL slow_query_log = 'ON';
SET GLOBAL long_query_time = 1;  -- Log queries > 1 second
SET GLOBAL slow_query_log_file = '/var/log/mysql/slow.log';

-- View slow queries
SHOW VARIABLES LIKE 'slow_query%';
```

### Query Analysis with EXPLAIN

**PostgreSQL EXPLAIN:**
```sql
-- Basic EXPLAIN
EXPLAIN SELECT * FROM users WHERE created_at > '2025-01-01';

-- EXPLAIN with actual execution
EXPLAIN ANALYZE
SELECT u.name, COUNT(o.id) as order_count
FROM users u
LEFT JOIN orders o ON u.id = o.user_id
WHERE u.created_at > '2025-01-01'
GROUP BY u.id, u.name
ORDER BY order_count DESC
LIMIT 10;

-- Look for:
-- - Seq Scan (sequential scan - slow for large tables)
-- - Index Scan (using index - good)
-- - Nested Loop (join method)
-- - Hash Join (join method for large datasets)
```

**Key EXPLAIN Terms:**
- **Seq Scan**: Full table scan (slow)
- **Index Scan**: Using index (fast)
- **Bitmap Index Scan**: Using multiple indexes
- **cost**: Estimated query cost
- **rows**: Estimated rows returned
- **actual time**: Real execution time

**MySQL EXPLAIN:**
```sql
EXPLAIN SELECT * FROM users WHERE email = 'user@example.com';

-- Extended information
EXPLAIN FORMAT=JSON SELECT ...;

-- Look for:
-- - type: ALL (full table scan - bad)
-- - type: index (using index - better)
-- - type: ref (index with equality - good)
-- - possible_keys: Available indexes
-- - key: Actual index used
```

### Index Optimization

**When to Add Indexes:**
```sql
-- Add index for frequently queried columns
CREATE INDEX idx_users_email ON users(email);

-- Compound index for multiple columns
CREATE INDEX idx_orders_user_status ON orders(user_id, status);

-- Partial index (PostgreSQL)
CREATE INDEX idx_active_users ON users(email) WHERE status = 'active';

-- Full-text search index
CREATE INDEX idx_posts_content ON posts USING gin(to_tsvector('english', content));
```

**Check Index Usage:**
```sql
-- PostgreSQL: Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
ORDER BY idx_scan ASC;

-- Find unused indexes
SELECT
    schemaname,
    tablename,
    indexname
FROM pg_stat_user_indexes
WHERE idx_scan = 0
AND indexrelname NOT LIKE 'pg_toast%';

-- MySQL: Check index usage
SELECT * FROM sys.schema_unused_indexes;
```

**Drop Unused Indexes:**
```sql
-- Unused indexes slow down writes
DROP INDEX idx_rarely_used;
```

### Query Optimization Techniques

**1. Avoid SELECT ***
```sql
-- BAD: Fetches all columns
SELECT * FROM users WHERE id = 123;

-- GOOD: Only needed columns
SELECT id, name, email FROM users WHERE id = 123;
```

**2. Use LIMIT**
```sql
-- BAD: Returns all rows
SELECT * FROM orders ORDER BY created_at DESC;

-- GOOD: Limit results
SELECT * FROM orders ORDER BY created_at DESC LIMIT 100;
```

**3. Optimize JOINs**
```sql
-- BAD: Unnecessary join
SELECT u.name
FROM users u
JOIN orders o ON u.id = o.user_id
WHERE u.id = 123;

-- GOOD: No join needed
SELECT name FROM users WHERE id = 123;
```

**4. Use EXISTS Instead of IN**
```sql
-- SLOW: IN with subquery
SELECT * FROM users
WHERE id IN (SELECT user_id FROM orders WHERE status = 'completed');

-- FASTER: EXISTS
SELECT * FROM users u
WHERE EXISTS (
    SELECT 1 FROM orders o
    WHERE o.user_id = u.id AND o.status = 'completed'
);
```

**5. Batch Operations**
```sql
-- BAD: Multiple single inserts
INSERT INTO users (name, email) VALUES ('John', 'john@example.com');
INSERT INTO users (name, email) VALUES ('Jane', 'jane@example.com');

-- GOOD: Single batch insert
INSERT INTO users (name, email) VALUES
    ('John', 'john@example.com'),
    ('Jane', 'jane@example.com');
```

---

## Data Integrity Issues

### Missing or Incorrect Data

**Debugging Steps:**

**1. Check Constraints**
```sql
-- View table constraints
SELECT * FROM information_schema.table_constraints
WHERE table_name = 'users';

-- Check for constraint violations
SELECT * FROM users WHERE email IS NULL;  -- If email should be NOT NULL
```

**2. Foreign Key Issues**
```sql
-- Check for orphaned records
SELECT o.*
FROM orders o
LEFT JOIN users u ON o.user_id = u.id
WHERE u.id IS NULL;

-- Find foreign key constraints
SELECT * FROM information_schema.table_constraints
WHERE constraint_type = 'FOREIGN KEY';
```

**3. Data Type Mismatches**
```sql
-- Check data types
SELECT column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE table_name = 'users';
```

### Duplicate Data

```sql
-- Find duplicates
SELECT email, COUNT(*) as count
FROM users
GROUP BY email
HAVING COUNT(*) > 1;

-- Remove duplicates (keep oldest)
DELETE FROM users
WHERE id NOT IN (
    SELECT MIN(id)
    FROM users
    GROUP BY email
);
```

### Data Validation

```sql
-- Check for invalid data
SELECT * FROM users WHERE email NOT LIKE '%@%';
SELECT * FROM products WHERE price < 0;
SELECT * FROM orders WHERE total != (quantity * unit_price);
```

---

## Transaction Problems

### Understanding Transactions

**ACID Properties:**
- **Atomicity**: All or nothing
- **Consistency**: Data remains valid
- **Isolation**: Transactions don't interfere
- **Durability**: Changes are permanent

### Transaction Isolation Levels

```sql
-- PostgreSQL isolation levels
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;  -- Lowest isolation
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;     -- Default
SET TRANSACTION ISOLATION LEVEL REPEATABLE READ;
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;       -- Highest isolation

-- Check current isolation level
SHOW TRANSACTION ISOLATION LEVEL;
```

**Isolation Level Issues:**

| Level | Dirty Read | Non-Repeatable Read | Phantom Read |
|-------|------------|---------------------|--------------|
| Read Uncommitted | Yes | Yes | Yes |
| Read Committed | No | Yes | Yes |
| Repeatable Read | No | No | Yes |
| Serializable | No | No | No |

### Transaction Debugging

**Find Long-Running Transactions:**
```sql
-- PostgreSQL
SELECT
    pid,
    now() - pg_stat_activity.xact_start AS duration,
    state,
    query
FROM pg_stat_activity
WHERE (now() - pg_stat_activity.xact_start) > interval '5 minutes'
ORDER BY duration DESC;

-- MySQL
SELECT *
FROM information_schema.innodb_trx
ORDER BY trx_started;
```

**Kill Stuck Transaction:**
```sql
-- PostgreSQL
SELECT pg_terminate_backend(pid);

-- MySQL
KILL <thread_id>;
```

### Transaction Best Practices

**1. Keep Transactions Short**
```python
# BAD: Long transaction
with session.begin():
    user = session.query(User).get(123)
    # ... lots of processing ...
    time.sleep(10)  # Holding transaction!
    user.status = 'processed'
    session.commit()

# GOOD: Short transaction
user = session.query(User).get(123)
# ... lots of processing ...
with session.begin():
    user.status = 'processed'
    session.commit()
```

**2. Handle Errors Properly**
```python
try:
    with session.begin():
        # Database operations
        session.add(new_user)
        session.commit()
except Exception as e:
    session.rollback()
    logging.error(f"Transaction failed: {e}")
    raise
```

---

## Lock and Deadlock Issues

### Identifying Locks

**PostgreSQL - Check Locks:**
```sql
-- View all locks
SELECT
    locktype,
    database,
    relation::regclass,
    mode,
    granted,
    pid
FROM pg_locks
WHERE NOT granted;

-- Find blocking queries
SELECT
    blocked_locks.pid AS blocked_pid,
    blocked_activity.usename AS blocked_user,
    blocking_locks.pid AS blocking_pid,
    blocking_activity.usename AS blocking_user,
    blocked_activity.query AS blocked_statement,
    blocking_activity.query AS blocking_statement
FROM pg_catalog.pg_locks blocked_locks
JOIN pg_catalog.pg_stat_activity blocked_activity ON blocked_activity.pid = blocked_locks.pid
JOIN pg_catalog.pg_locks blocking_locks ON blocking_locks.locktype = blocked_locks.locktype
    AND blocking_locks.database IS NOT DISTINCT FROM blocked_locks.database
    AND blocking_locks.relation IS NOT DISTINCT FROM blocked_locks.relation
    AND blocking_locks.page IS NOT DISTINCT FROM blocked_locks.page
    AND blocking_locks.tuple IS NOT DISTINCT FROM blocked_locks.tuple
    AND blocking_locks.virtualxid IS NOT DISTINCT FROM blocked_locks.virtualxid
    AND blocking_locks.transactionid IS NOT DISTINCT FROM blocked_locks.transactionid
    AND blocking_locks.classid IS NOT DISTINCT FROM blocked_locks.classid
    AND blocking_locks.objid IS NOT DISTINCT FROM blocked_locks.objid
    AND blocking_locks.objsubid IS NOT DISTINCT FROM blocked_locks.objsubid
    AND blocking_locks.pid != blocked_locks.pid
JOIN pg_catalog.pg_stat_activity blocking_activity ON blocking_activity.pid = blocking_locks.pid
WHERE NOT blocked_locks.granted;
```

**MySQL - Check Locks:**
```sql
-- InnoDB locks
SELECT * FROM information_schema.innodb_locks;

-- Lock waits
SELECT * FROM information_schema.innodb_lock_waits;

-- Transactions
SELECT * FROM information_schema.innodb_trx;
```

### Deadlock Detection

**Deadlock Example:**
```
Transaction 1:
1. Locks row A
2. Tries to lock row B (waits)

Transaction 2:
1. Locks row B
2. Tries to lock row A (waits)

Result: Deadlock! Neither can proceed.
```

**View Deadlocks:**
```sql
-- PostgreSQL: Enable deadlock logging
ALTER SYSTEM SET log_lock_waits = on;
ALTER SYSTEM SET deadlock_timeout = '1s';

-- MySQL: Check innodb status
SHOW ENGINE INNODB STATUS;
-- Look for "LATEST DETECTED DEADLOCK" section
```

### Preventing Deadlocks

**1. Lock in Consistent Order**
```python
# BAD: Inconsistent lock order
# Transaction 1: Lock user 123, then user 456
# Transaction 2: Lock user 456, then user 123
# DEADLOCK!

# GOOD: Always lock in same order
user_ids = sorted([123, 456])
for user_id in user_ids:
    user = session.query(User).with_for_update().get(user_id)
    # Process user
```

**2. Use Row-Level Locking**
```sql
-- Lock specific rows, not entire table
SELECT * FROM users
WHERE id = 123
FOR UPDATE;  -- Row-level lock
```

**3. Keep Transactions Short**
```python
# Minimize time holding locks
with session.begin():
    user = session.query(User).with_for_update().get(123)
    user.balance += 100
    session.commit()
# Lock released immediately after commit
```

---

## Replication and Sync Issues

### Replication Lag

**Check Replication Status:**
```sql
-- PostgreSQL: Check replication lag
SELECT
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    replay_lsn,
    sync_state,
    pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes
FROM pg_stat_replication;

-- MySQL: Check replica status
SHOW REPLICA STATUS\G
-- Look for Seconds_Behind_Master
```

**Common Replication Issues:**

**1. Network Latency**
- Symptom: High replication lag
- Solution: Check network between master and replica

**2. Replica Can't Keep Up**
- Symptom: Continuously increasing lag
- Solution: Scale replica hardware or reduce write load

**3. Replication Stopped**
- Symptom: Replication not running
- Solution: Check error logs, restart replication

---

## Database-Specific Debugging

### PostgreSQL-Specific

**Vacuum Issues:**
```sql
-- Check table bloat
SELECT
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;

-- Manual vacuum
VACUUM ANALYZE users;
VACUUM FULL users;  -- Locks table!
```

**Connection Pooling with pgBouncer:**
```ini
# pgbouncer.ini
[databases]
mydb = host=localhost dbname=mydb

[pgbouncer]
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 20
```

### MySQL-Specific

**InnoDB Buffer Pool:**
```sql
-- Check buffer pool size
SHOW VARIABLES LIKE 'innodb_buffer_pool_size';

-- Buffer pool hit ratio (should be > 99%)
SHOW STATUS LIKE 'Innodb_buffer_pool_read%';
```

**Query Cache (deprecated in MySQL 8.0):**
```sql
-- Check query cache
SHOW VARIABLES LIKE 'query_cache%';
SHOW STATUS LIKE 'Qcache%';
```

### MongoDB-Specific

**Check Query Performance:**
```javascript
// Explain query
db.users.find({ email: "user@example.com" }).explain("executionStats")

// Check indexes
db.users.getIndexes()

// Profile slow queries
db.setProfilingLevel(1, { slowms: 100 })  // Log queries > 100ms
db.system.profile.find().sort({ ts: -1 }).limit(5)
```

---

## Monitoring and Tools

### Essential Monitoring

**Key Metrics to Track:**
- Query execution time (p50, p95, p99)
- Connection pool usage
- Transaction throughput
- Lock wait time
- Replication lag
- Cache hit ratio
- Disk I/O

### Monitoring Tools

**PostgreSQL:**
- `pg_stat_statements` - Query statistics
- `pgBadger` - Log analyzer
- `pg_top` - Real-time monitoring

**MySQL:**
- `mysqldumpslow` - Slow query analyzer
- `pt-query-digest` - Percona Toolkit
- `mysqltuner` - Configuration tuning

**Universal:**
- `DataDog` - Application monitoring
- `New Relic` - APM
- `Prometheus + Grafana` - Metrics

### Debugging Tools

**Command Line:**
```bash
# PostgreSQL
psql -U username -d database
\dt  # List tables
\d tablename  # Describe table
\x  # Expanded display

# MySQL
mysql -u username -p database
SHOW TABLES;
DESCRIBE tablename;
```

**GUI Tools:**
- pgAdmin (PostgreSQL)
- MySQL Workbench
- DBeaver (universal)
- TablePlus (universal)

---

## Summary

**Database Debugging Checklist:**

✅ **Connection Issues:**
- Verify database is running
- Check credentials and permissions
- Monitor connection pool usage

✅ **Performance:**
- Use EXPLAIN to analyze queries
- Add appropriate indexes
- Monitor slow query logs

✅ **Data Integrity:**
- Validate constraints
- Check for orphaned records
- Monitor transaction logs

✅ **Locking:**
- Watch for long-running transactions
- Detect and resolve deadlocks
- Use appropriate isolation levels

✅ **Monitoring:**
- Track key metrics
- Set up alerts
- Regular performance reviews

**Remember:** Database debugging requires patience and systematic investigation. Always measure before and after changes to verify improvements.
