#!/usr/bin/env python3
"""
Error Frequency Analyzer - Track error occurrence patterns over time

Analyzes error patterns to identify:
- Error frequency trends
- Spike detection
- Recurring error patterns
- Error correlation with time periods
- Statistical anomaly detection

Usage:
    python error_frequency.py <log_file> [--window <minutes>] [--threshold <count>]
"""

import sys
import re
from collections import defaultdict
from datetime import datetime, timedelta
import argparse
from typing import Dict, List, Tuple

class ErrorFrequencyAnalyzer:
    def __init__(self, log_file: str, window_minutes: int = 60, threshold: int = 5):
        self.log_file = log_file
        self.window_minutes = window_minutes
        self.threshold = threshold
        self.error_timeline = defaultdict(list)  # timestamp -> error messages
        self.error_types = defaultdict(int)
        
    def parse_timestamp(self, line: str) -> datetime:
        """Extract and parse timestamp from log line"""
        timestamp_patterns = [
            # 2025-01-15 14:30:45
            r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})',
            # 2025-01-15T14:30:45Z
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
            # [2025-01-15 14:30:45]
            r'\[(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\]',
        ]
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, line)
            if match:
                try:
                    timestamp_str = match.group(1).replace('T', ' ').rstrip('Z')
                    return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                except:
                    continue
        return None
    
    def extract_error_type(self, line: str) -> str:
        """Extract error type/category from line"""
        error_keywords = [
            'NullPointerException', 'IndexOutOfBounds', 'TypeError', 
            'ValueError', 'KeyError', 'AttributeError', 'ConnectionError',
            'TimeoutError', 'MemoryError', 'SyntaxError', 'ImportError',
            '404', '500', '503', 'ERROR', 'EXCEPTION', 'FAILURE'
        ]
        
        line_upper = line.upper()
        for keyword in error_keywords:
            if keyword.upper() in line_upper:
                return keyword
        
        return "GENERIC_ERROR"
    
    def analyze(self) -> bool:
        """Analyze log file for error frequency patterns"""
        try:
            with open(self.log_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    # Check if line contains error indicators
                    if not any(indicator in line.upper() for indicator in 
                              ['ERROR', 'EXCEPTION', 'FATAL', 'CRITICAL', 'FAIL']):
                        continue
                    
                    timestamp = self.parse_timestamp(line)
                    if not timestamp:
                        continue
                    
                    error_type = self.extract_error_type(line)
                    
                    # Round to window boundaries for grouping
                    window_key = timestamp.replace(
                        minute=(timestamp.minute // self.window_minutes) * self.window_minutes,
                        second=0,
                        microsecond=0
                    )
                    
                    self.error_timeline[window_key].append({
                        'type': error_type,
                        'timestamp': timestamp,
                        'message': line.strip()[:200]
                    })
                    
                    self.error_types[error_type] += 1
            
            return len(self.error_timeline) > 0
            
        except FileNotFoundError:
            print(f"❌ Error: File '{self.log_file}' not found")
            return False
        except Exception as e:
            print(f"❌ Error analyzing file: {e}")
            return False
    
    def detect_spikes(self) -> List[Tuple[datetime, int, float]]:
        """Detect error spikes (periods with unusually high error rates)"""
        if not self.error_timeline:
            return []
        
        # Calculate average error rate
        error_counts = [len(errors) for errors in self.error_timeline.values()]
        avg_rate = sum(error_counts) / len(error_counts) if error_counts else 0
        std_dev = (sum((x - avg_rate) ** 2 for x in error_counts) / len(error_counts)) ** 0.5
        
        # Spike threshold: mean + 2*std_dev
        spike_threshold = avg_rate + (2 * std_dev)
        
        spikes = []
        for window_time, errors in sorted(self.error_timeline.items()):
            error_count = len(errors)
            if error_count >= spike_threshold and error_count >= self.threshold:
                deviation = (error_count - avg_rate) / std_dev if std_dev > 0 else 0
                spikes.append((window_time, error_count, deviation))
        
        return sorted(spikes, key=lambda x: x[1], reverse=True)
    
    def find_recurring_patterns(self) -> Dict[str, List[datetime]]:
        """Identify errors that occur repeatedly"""
        recurring = defaultdict(list)
        
        for window_time, errors in self.error_timeline.items():
            for error in errors:
                error_type = error['type']
                recurring[error_type].append(window_time)
        
        # Filter to only recurring patterns (>= threshold)
        return {k: v for k, v in recurring.items() if len(v) >= self.threshold}
    
    def print_report(self):
        """Print comprehensive frequency analysis report"""
        print("\n" + "="*80)
        print(f"ERROR FREQUENCY ANALYSIS: {self.log_file}")
        print(f"Analysis Window: {self.window_minutes} minutes | Threshold: {self.threshold}")
        print("="*80 + "\n")
        
        # Overall Statistics
        total_windows = len(self.error_timeline)
        total_errors = sum(len(errors) for errors in self.error_timeline.values())
        
        if total_errors == 0:
            print("✅ No errors found in the analyzed timeframe.\n")
            return
        
        avg_errors_per_window = total_errors / total_windows if total_windows > 0 else 0
        
        print(f"📊 OVERALL STATISTICS:")
        print(f"  Total Error Count: {total_errors}")
        print(f"  Time Windows Analyzed: {total_windows}")
        print(f"  Average Errors per {self.window_minutes}min: {avg_errors_per_window:.1f}")
        
        if self.error_timeline:
            first_error = min(self.error_timeline.keys())
            last_error = max(self.error_timeline.keys())
            print(f"  First Error: {first_error.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"  Last Error: {last_error.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Error Types Distribution
        print(f"\n🔍 ERROR TYPES DISTRIBUTION:")
        for error_type, count in sorted(self.error_types.items(), 
                                        key=lambda x: x[1], reverse=True)[:10]:
            percentage = (count / total_errors * 100) if total_errors > 0 else 0
            bar = '█' * int(percentage / 2)
            print(f"  {error_type:25s}: {count:5d} ({percentage:5.1f}%) {bar}")
        
        # Spike Detection
        spikes = self.detect_spikes()
        if spikes:
            print(f"\n🚨 ERROR SPIKES DETECTED ({len(spikes)} spikes):")
            for i, (spike_time, count, deviation) in enumerate(spikes[:10], 1):
                print(f"\n  {i}. {spike_time.strftime('%Y-%m-%d %H:%M')} - {count} errors")
                print(f"     Severity: {deviation:.1f}σ above average")
                
                # Show error types in this spike
                errors_in_spike = self.error_timeline[spike_time]
                error_type_counts = defaultdict(int)
                for error in errors_in_spike:
                    error_type_counts[error['type']] += 1
                
                print(f"     Error types: {dict(error_type_counts)}")
        else:
            print("\n✅ No significant error spikes detected")
        
        # Recurring Patterns
        recurring = self.find_recurring_patterns()
        if recurring:
            print(f"\n🔄 RECURRING ERROR PATTERNS:")
            for error_type, occurrences in sorted(recurring.items(), 
                                                  key=lambda x: len(x[1]), 
                                                  reverse=True)[:5]:
                print(f"\n  {error_type}: {len(occurrences)} occurrences")
                print(f"     Time windows: {occurrences[0].strftime('%H:%M')} to " +
                      f"{occurrences[-1].strftime('%H:%M')}")
                
                # Calculate frequency pattern
                time_diffs = []
                for i in range(1, len(occurrences)):
                    diff = (occurrences[i] - occurrences[i-1]).total_seconds() / 60
                    time_diffs.append(diff)
                
                if time_diffs:
                    avg_interval = sum(time_diffs) / len(time_diffs)
                    print(f"     Average interval: {avg_interval:.1f} minutes")
        
        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        
        if spikes:
            print("  🚨 CRITICAL: Error spikes detected!")
            print("     1. Investigate the time periods with highest error rates")
            print("     2. Check for deployment or config changes at spike times")
            print("     3. Review system resource usage during spike periods")
        
        if recurring:
            print("  ⚠️  Recurring error patterns found:")
            print("     1. These errors may indicate systemic issues")
            print("     2. Review error types that occur repeatedly")
            print("     3. Consider implementing permanent fixes")
        
        error_rate = total_errors / total_windows if total_windows > 0 else 0
        if error_rate > 10:
            print("  ⚠️  High error rate detected:")
            print("     1. Error rate exceeds normal thresholds")
            print("     2. System health may be compromised")
            print("     3. Immediate investigation recommended")
        
        print("\n  📋 Next Steps:")
        print("     1. Focus on the most frequent error types")
        print("     2. Investigate error spikes for root causes")
        print("     3. Check correlation with system events (deployments, traffic spikes)")
        print("     4. Review error messages for specific failure points")
        
        print("\n" + "="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description='Analyze error frequency patterns in log files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Analyze with default 60-minute windows
  python error_frequency.py app.log
  
  # Use 30-minute windows
  python error_frequency.py app.log --window 30
  
  # Only flag spikes with 10+ errors
  python error_frequency.py app.log --threshold 10
        '''
    )
    
    parser.add_argument('log_file', help='Path to log file')
    parser.add_argument('--window', type=int, default=60,
                       help='Time window in minutes for grouping errors (default: 60)')
    parser.add_argument('--threshold', type=int, default=5,
                       help='Minimum error count to flag as spike (default: 5)')
    
    args = parser.parse_args()
    
    analyzer = ErrorFrequencyAnalyzer(
        args.log_file,
        window_minutes=args.window,
        threshold=args.threshold
    )
    
    if analyzer.analyze():
        analyzer.print_report()
        sys.exit(0)
    else:
        print("❌ Analysis failed - no errors found or file inaccessible")
        sys.exit(1)

if __name__ == '__main__':
    main()
