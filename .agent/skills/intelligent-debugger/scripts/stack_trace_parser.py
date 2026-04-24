#!/usr/bin/env python3
"""
Stack Trace Parser - Parse and explain stack traces

Analyzes stack traces to:
- Identify error type and location
- Explain the call chain
- Suggest likely causes
- Provide debugging hints

Usage:
    python stack_trace_parser.py <file_with_stack_trace>
    OR
    echo "stack trace" | python stack_trace_parser.py
"""

import sys
import re

ERROR_EXPLANATIONS = {
    'KeyError': 'Dictionary key not found. Check if key exists before accessing or use dict.get()',
    'IndexError': 'List index out of range. Verify array length before accessing',
    'TypeError': 'Operation on incompatible types. Check data types and conversions',
    'ValueError': 'Invalid value for operation. Validate input data',
    'AttributeError': 'Object does not have attribute. Check object type and available attributes',
    'NameError': 'Variable not defined. Check variable name spelling and scope',
    'ImportError': 'Module not found. Verify module is installed and import path is correct',
    'FileNotFoundError': 'File does not exist. Check file path and permissions',
    'ConnectionError': 'Network connection failed. Verify service is running and reachable',
    'TimeoutError': 'Operation took too long. Check performance or increase timeout',
    'PermissionError': 'Access denied. Check file/directory permissions',
    'ZeroDivisionError': 'Division by zero. Add check for denominator != 0',
    'MemoryError': 'Out of memory. Optimize memory usage or increase available RAM',
    'RecursionError': 'Maximum recursion depth exceeded. Check for infinite recursion',
    'RuntimeError': 'Generic runtime error. Review error message for specifics'
}

def parse_python_traceback(text):
    """Parse Python stack trace"""
    lines = text.strip().split('\n')
    
    # Find error type
    error_line = lines[-1] if lines else ""
    error_match = re.match(r'(\w+Error|Exception):\s*(.*)', error_line)
    
    if not error_match:
        return None
    
    error_type = error_match.group(1)
    error_message = error_match.group(2)
    
    # Parse call stack
    call_stack = []
    for i, line in enumerate(lines):
        if line.strip().startswith('File '):
            file_match = re.search(r'File "([^"]+)", line (\d+)(?:, in (.+))?', line)
            if file_match:
                file_path = file_match.group(1)
                line_no = file_match.group(2)
                function = file_match.group(3) or '<module>'
                
                # Get the code line (usually next line)
                code_line = ""
                if i + 1 < len(lines):
                    code_line = lines[i + 1].strip()
                
                call_stack.append({
                    'file': file_path,
                    'line': line_no,
                    'function': function,
                    'code': code_line
                })
    
    return {
        'language': 'Python',
        'error_type': error_type,
        'error_message': error_message,
        'call_stack': call_stack
    }

def parse_javascript_traceback(text):
    """Parse JavaScript/Node.js stack trace"""
    lines = text.strip().split('\n')
    
    # Usually first line is the error
    error_line = lines[0] if lines else ""
    error_match = re.match(r'(\w+Error|Error):\s*(.*)', error_line)
    
    if not error_match:
        return None
    
    error_type = error_match.group(1)
    error_message = error_match.group(2)
    
    # Parse call stack (lines starting with "at")
    call_stack = []
    for line in lines[1:]:
        if line.strip().startswith('at '):
            # at functionName (file:line:col)
            match = re.search(r'at\s+([^\(]+)\s*\(([^:]+):(\d+):(\d+)\)', line)
            if match:
                call_stack.append({
                    'function': match.group(1).strip(),
                    'file': match.group(2),
                    'line': match.group(3),
                    'column': match.group(4)
                })
    
    return {
        'language': 'JavaScript',
        'error_type': error_type,
        'error_message': error_message,
        'call_stack': call_stack
    }

def explain_error(parsed):
    """Generate explanation and recommendations"""
    print("\n" + "="*80)
    print("STACK TRACE ANALYSIS")
    print("="*80 + "\n")
    
    print(f"🔴 ERROR TYPE: {parsed['error_type']}")
    print(f"📝 MESSAGE: {parsed['error_message']}\n")
    
    # Error explanation
    explanation = ERROR_EXPLANATIONS.get(parsed['error_type'], 
                                        'Review error message for specific details')
    print(f"💡 EXPLANATION:\n   {explanation}\n")
    
    # Call stack
    if parsed['call_stack']:
        print("📚 CALL STACK (most recent call last):")
        for i, frame in enumerate(reversed(parsed['call_stack']), 1):
            print(f"\n  {i}. {frame.get('function', 'unknown')}")
            print(f"     File: {frame.get('file', 'unknown')}, Line: {frame.get('line', '?')}")
            if 'code' in frame and frame['code']:
                print(f"     Code: {frame['code']}")
    
    # Root location (where error occurred)
    if parsed['call_stack']:
        root = parsed['call_stack'][-1]
        print(f"\n🎯 ROOT LOCATION:")
        print(f"   File: {root.get('file', 'unknown')}")
        print(f"   Line: {root.get('line', '?')}")
        print(f"   Function: {root.get('function', 'unknown')}")
    
    # Debugging suggestions
    print(f"\n🔍 DEBUGGING SUGGESTIONS:")
    suggestions = get_debugging_suggestions(parsed)
    for i, suggestion in enumerate(suggestions, 1):
        print(f"   {i}. {suggestion}")
    
    print("\n" + "="*80 + "\n")

def get_debugging_suggestions(parsed):
    """Get specific debugging suggestions based on error type"""
    error_type = parsed['error_type']
    suggestions = []
    
    if error_type == 'KeyError':
        suggestions = [
            "Check if the key exists before accessing: if 'key' in dict:",
            "Use dict.get('key', default_value) for safe access",
            "Print dictionary keys to verify available keys",
            "Check for typos in the key name"
        ]
    elif error_type == 'IndexError':
        suggestions = [
            "Check array length before accessing: if len(array) > index:",
            "Use enumerate() to iterate safely",
            "Verify the array is populated with expected data",
            "Check for off-by-one errors in index calculations"
        ]
    elif error_type == 'TypeError':
        suggestions = [
            "Print variable types to verify: print(type(variable))",
            "Check if variables are initialized properly",
            "Verify function arguments are correct types",
            "Look for None values being used incorrectly"
        ]
    elif 'Connection' in error_type or 'Timeout' in error_type:
        suggestions = [
            "Verify the service/server is running",
            "Check network connectivity and firewall rules",
            "Verify URL/endpoint is correct",
            "Check for rate limiting or service outages"
        ]
    else:
        suggestions = [
            "Add print statements before the error line",
            "Check recent changes to related code",
            "Review error message for specific details",
            "Test with simpler input data"
        ]
    
    return suggestions

def main():
    # Read input from file or stdin
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1], 'r') as f:
                text = f.read()
        except FileNotFoundError:
            print(f"❌ File not found: {sys.argv[1]}")
            sys.exit(1)
    else:
        text = sys.stdin.read()
    
    # Try to parse as Python or JavaScript
    parsed = parse_python_traceback(text)
    if not parsed:
        parsed = parse_javascript_traceback(text)
    
    if parsed:
        explain_error(parsed)
    else:
        print("❌ Could not parse stack trace. Supported formats:")
        print("   - Python tracebacks")
        print("   - JavaScript/Node.js stack traces")
        sys.exit(1)

if __name__ == '__main__':
    main()
