#!/usr/bin/env python3
"""
Log Analyzer - Automated log file analysis for debugging

Analyzes log files to identify:
- Error frequency and patterns
- Common error messages
- Timeline of issues
- Anomaly detection
- Error clustering

Usage:
    python log_analyzer.py <log_file> [--errors-only] [--last-hours <hours>]
"""

import sys
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import argparse

class LogAnalyzer:
    def __init__(self, log_file, errors_only=False, last_hours=None):
        self.log_file = log_file
        self.errors_only = errors_only
        self.last_hours = last_hours
        self.error_patterns = []
        self.log_levels = Counter()
        self.error_messages = Counter()
        self.timeline = defaultdict(int)
        
    def parse_line(self, line):
        """Parse a log line and extract key information"""
        # Common log patterns
        patterns = [
            # Standard format: 2025-01-15 14:30:45 [ERROR] Message
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}).*?\[(\w+)\]\s+(.*)',
            # ISO format: 2025-01-15T14:30:45Z [ERROR] Message
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[Z]?).*?\[(\w+)\]\s+(.*)',
            # Simple format: ERROR: Message
            r'(\w+):\s+(.*)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                if len(match.groups()) == 3:
                    timestamp, level, message = match.groups()
                    return {'timestamp': timestamp, 'level': level, 'message': message}
                elif len(match.groups()) == 2:
                    level, message = match.groups()
                    return {'timestamp': None, 'level': level, 'message': message}
        
        return None
    
    def is_within_timeframe(self, timestamp):
        """Check if timestamp is within the requested timeframe"""
        if not self.last_hours or not timestamp:
            return True
        
        try:
            log_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            cutoff = datetime.now() - timedelta(hours=self.last_hours)
            return log_time >= cutoff
        except:
            return True
    
    def analyze(self):
        """Analyze the log file"""
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    parsed = self.parse_line(line)
                    if not parsed:
                        continue
                    
                    level = parsed['level'].upper()
                    
                    # Filter by errors if requested
                    if self.errors_only and level not in ['ERROR', 'CRITICAL', 'FATAL']:
                        continue
                    
                    # Filter by time if requested
                    if not self.is_within_timeframe(parsed['timestamp']):
                        continue
                    
                    # Count log levels
                    self.log_levels[level] += 1
                    
                    # Track error messages
                    if level in ['ERROR', 'CRITICAL', 'FATAL', 'EXCEPTION']:
                        # Clean and normalize message
                        message = parsed['message'][:200]  # First 200 chars
                        self.error_messages[message] += 1
                    
                    # Build timeline (by hour)
                    if parsed['timestamp']:
                        try:
                            hour = parsed['timestamp'][:13]  # YYYY-MM-DD HH
                            self.timeline[hour] += 1
                        except:
                            pass
            
            return True
        except FileNotFoundError:
            print(f"❌ Error: File '{self.log_file}' not found")
            return False
        except Exception as e:
            print(f"❌ Error analyzing log: {e}")
            return False
    
    def print_report(self):
        """Print analysis report"""
        print("\n" + "="*80)
        print(f"LOG ANALYSIS REPORT: {self.log_file}")
        print("="*80 + "\n")        
        # Log Levels Summary
        print("📊 LOG LEVELS:")
        total_logs = sum(self.log_levels.values())
        for level, count in self.log_levels.most_common():
            percentage = (count / total_logs * 100) if total_logs > 0 else 0
            print(f"  {level:15s}: {count:6d} ({percentage:5.1f}%)")
        print(f"  {'TOTAL':15s}: {total_logs:6d}\n")
        
        # Top Errors
        if self.error_messages:
            print("🚨 TOP ERROR MESSAGES:")
            for i, (message, count) in enumerate(self.error_messages.most_common(10), 1):
                print(f"\n  {i}. Occurred {count} time(s):")
                print(f"     {message[:150]}...")
        else:
            print("✅ No errors found in log file\n")
        
        # Timeline
        if self.timeline:
            print("\n📅 ERROR TIMELINE (by hour):")
            sorted_timeline = sorted(self.timeline.items())
            for timestamp, count in sorted_timeline[-20:]:  # Last 20 hours
                bar = '█' * min(count // 10, 50)
                print(f"  {timestamp}: {bar} ({count})")
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        error_count = sum(v for k, v in self.log_levels.items() 
                         if k in ['ERROR', 'CRITICAL', 'FATAL'])
        
        if error_count == 0:
            print("  ✅ No errors detected. System appears healthy.")
        elif error_count < 10:
            print("  ⚠️  Few errors detected. Review error messages above.")
        elif error_count < 100:
            print("  ⚠️  Moderate error rate. Investigate top error patterns.")
        else:
            print("  🚨 High error rate! Immediate investigation recommended.")
        
        # Pattern suggestions
        if self.error_messages:
            print("\n  📋 Suggested next steps:")
            print("  1. Review top 3 most frequent errors")
            print("  2. Check if errors cluster around specific times")
            print("  3. Search codebase for error message text")
            print("  4. Check recent deployments or config changes")
        
        print("\n" + "="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description='Analyze log files for debugging',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python log_analyzer.py app.log
  python log_analyzer.py app.log --errors-only
  python log_analyzer.py app.log --last-hours 24
        '''
    )
    
    parser.add_argument('log_file', help='Path to log file')
    parser.add_argument('--errors-only', action='store_true',
                       help='Show only errors (ERROR, CRITICAL, FATAL)')
    parser.add_argument('--last-hours', type=int,
                       help='Only analyze logs from last N hours')
    
    args = parser.parse_args()
    
    analyzer = LogAnalyzer(
        args.log_file,
        errors_only=args.errors_only,
        last_hours=args.last_hours
    )
    
    if analyzer.analyze():
        analyzer.print_report()
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == '__main__':
    main()
