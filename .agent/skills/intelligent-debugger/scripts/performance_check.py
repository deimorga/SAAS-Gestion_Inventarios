#!/usr/bin/env python3
"""
Performance Check - Quick performance metrics analysis

Checks:
- Response time statistics
- Memory usage
- CPU utilization
- Resource bottlenecks

Usage:
    python performance_check.py [--url <url>] [--iterations <n>]
"""

import sys
import time
import psutil
import argparse
from statistics import mean, median, stdev

def check_system_resources():
    """Check current system resource usage"""
    print("\n📊 SYSTEM RESOURCES:")
    print("="*60)
    
    # CPU
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count()
    print(f"CPU Usage: {cpu_percent}% ({cpu_count} cores)")
    
    # Memory
    memory = psutil.virtual_memory()
    print(f"Memory: {memory.percent}% used ({memory.used // 1024**3}GB / {memory.total // 1024**3}GB)")
    
    # Disk
    disk = psutil.disk_usage('/')
    print(f"Disk: {disk.percent}% used ({disk.used // 1024**3}GB / {disk.total // 1024**3}GB)")
    
    # Recommendations
    print("\n💡 ANALYSIS:")
    if cpu_percent > 80:
        print("  🚨 HIGH CPU usage! Check for CPU-intensive processes")
    elif cpu_percent > 60:
        print("  ⚠️  Moderate CPU usage. Monitor for increases")
    else:
        print("  ✅ CPU usage is healthy")
    
    if memory.percent > 85:
        print("  🚨 HIGH memory usage! Check for memory leaks")
    elif memory.percent > 70:
        print("  ⚠️  Moderate memory usage. Monitor for increases")
    else:
        print("  ✅ Memory usage is healthy")
    
    if disk.percent > 90:
        print("  🚨 Disk space critical! Clean up or expand storage")
    elif disk.percent > 75:
        print("  ⚠️  Disk space running low")
    else:
        print("  ✅ Disk space is adequate")

def check_response_time(url, iterations=10):
    """Check HTTP endpoint response times"""
    try:
        import requests
    except ImportError:
        print("❌ requests library not installed. Run: pip install requests")
        return
    
    print(f"\n⏱️  RESPONSE TIME CHECK: {url}")
    print("="*60)
    print(f"Testing with {iterations} requests...\n")
    
    times = []
    success_count = 0
    
    for i in range(iterations):
        try:
            start = time.time()
            response = requests.get(url, timeout=10)
            elapsed = (time.time() - start) * 1000  # Convert to ms
            
            times.append(elapsed)
            if response.status_code == 200:
                success_count += 1
            
            print(f"  Request {i+1}: {elapsed:.2f}ms (Status: {response.status_code})")
        except requests.exceptions.RequestException as e:
            print(f"  Request {i+1}: FAILED - {e}")
    
    if times:
        print(f"\n📊 STATISTICS:")
        print(f"  Success Rate: {success_count}/{iterations} ({success_count/iterations*100:.1f}%)")
        print(f"  Mean: {mean(times):.2f}ms")
        print(f"  Median: {median(times):.2f}ms")
        if len(times) > 1:
            print(f"  Std Dev: {stdev(times):.2f}ms")
        print(f"  Min: {min(times):.2f}ms")
        print(f"  Max: {max(times):.2f}ms")
        
        print("\n💡 ANALYSIS:")
        avg_time = mean(times)
        if avg_time < 100:
            print("  ✅ Excellent response time!")
        elif avg_time < 300:
            print("  ✅ Good response time")
        elif avg_time < 1000:
            print("  ⚠️  Acceptable but could be optimized")
        else:
            print("  🚨 Slow response time! Optimization needed")
        
        if len(times) > 1:
            variation = stdev(times) / mean(times) * 100
            if variation > 30:
                print("  ⚠️  High variability - investigate inconsistent performance")

def check_process(process_name=None):
    """Check specific process resource usage"""
    print("\n🔍 PROCESS CHECK:")
    print("="*60)
    
    if process_name:
        found = False
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            if process_name.lower() in proc.info['name'].lower():
                found = True
                print(f"Process: {proc.info['name']} (PID: {proc.info['pid']})")
                print(f"  CPU: {proc.info['cpu_percent']}%")
                print(f"  Memory: {proc.info['memory_percent']:.2f}%")
        
        if not found:
            print(f"❌ Process '{process_name}' not found")
    else:
        # Show top 5 processes by CPU
        print("Top 5 processes by CPU:")
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                processes.append((proc.info['name'], proc.info['cpu_percent']))
            except:
                pass
        
        for name, cpu in sorted(processes, key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {name}: {cpu}%")

def main():
    parser = argparse.ArgumentParser(description='Performance check for debugging')
    parser.add_argument('--url', help='URL to check response time')
    parser.add_argument('--iterations', type=int, default=10,
                       help='Number of requests to make (default: 10)')
    parser.add_argument('--process', help='Process name to monitor')
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("PERFORMANCE CHECK")
    print("="*60)
    
    # Always check system resources
    check_system_resources()
    
    # Check URL if provided
    if args.url:
        check_response_time(args.url, args.iterations)
    
    # Check process if provided
    if args.process:
        check_process(args.process)
    
    print("\n" + "="*60 + "\n")

if __name__ == '__main__':
    main()
