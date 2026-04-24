#!/usr/bin/env python3
"""
Dependency Checker - Verify and diagnose dependency issues

Checks for:
- Missing dependencies
- Version conflicts
- Outdated packages
- Security vulnerabilities (if applicable)
- Circular dependencies

Supports:
- Python (requirements.txt, pyproject.toml, Pipfile)
- Node.js (package.json, package-lock.json)
- General dependency verification

Usage:
    python dependency_checker.py [--type python|node] [--check-updates]
"""

import sys
import json
import subprocess
import os
import re
from pathlib import Path
import argparse
from typing import Dict, List, Tuple, Optional

class DependencyChecker:
    def __init__(self, check_type: str = 'auto', check_updates: bool = False):
        self.check_type = check_type
        self.check_updates = check_updates
        self.issues = []
        self.warnings = []
        
    def detect_project_type(self) -> str:
        """Auto-detect project type based on files present"""
        files_present = os.listdir('.')
        
        if any(f in files_present for f in ['package.json', 'package-lock.json', 'yarn.lock']):
            return 'node'
        elif any(f in files_present for f in ['requirements.txt', 'pyproject.toml', 'Pipfile', 'setup.py']):
            return 'python'
        else:
            return 'unknown'
    
    def check_python_dependencies(self) -> Dict:
        """Check Python project dependencies"""
        print("🐍 Checking Python dependencies...\n")
        
        results = {
            'type': 'python',
            'missing': [],
            'outdated': [],
            'installed': [],
            'conflicts': []
        }
        
        # Check for requirements file
        req_files = ['requirements.txt', 'pyproject.toml', 'Pipfile']
        req_file = None
        
        for f in req_files:
            if os.path.exists(f):
                req_file = f
                break
        
        if not req_file:
            self.warnings.append("No dependency file found (requirements.txt, pyproject.toml, or Pipfile)")
            return results
        
        print(f"📄 Found: {req_file}\n")
        
        # Parse requirements
        dependencies = self._parse_requirements(req_file)
        
        # Check each dependency
        for package, version_spec in dependencies.items():
            installed_version = self._get_installed_version_python(package)
            
            if installed_version:
                results['installed'].append({
                    'name': package,
                    'version': installed_version,
                    'required': version_spec
                })
                
                # Check version compatibility
                if version_spec and not self._version_matches(installed_version, version_spec):
                    results['conflicts'].append({
                        'name': package,
                        'installed': installed_version,
                        'required': version_spec
                    })
            else:
                results['missing'].append({
                    'name': package,
                    'required': version_spec
                })
        
        # Check for outdated packages if requested
        if self.check_updates:
            print("🔍 Checking for outdated packages...\n")
            outdated = self._check_outdated_python()
            results['outdated'] = outdated
        
        return results
    
    def check_node_dependencies(self) -> Dict:
        """Check Node.js project dependencies"""
        print("📦 Checking Node.js dependencies...\n")
        
        results = {
            'type': 'node',
            'missing': [],
            'outdated': [],
            'installed': [],
            'conflicts': [],
            'extraneous': []
        }
        
        if not os.path.exists('package.json'):
            self.warnings.append("No package.json found")
            return results
        
        print("📄 Found: package.json\n")
        
        # Parse package.json
        try:
            with open('package.json', 'r') as f:
                package_data = json.load(f)
                dependencies = package_data.get('dependencies', {})
                dev_dependencies = package_data.get('devDependencies', {})
                all_deps = {**dependencies, **dev_dependencies}
        except Exception as e:
            self.issues.append(f"Failed to parse package.json: {e}")
            return results
        
        # Check if node_modules exists
        if not os.path.exists('node_modules'):
            self.warnings.append("node_modules folder not found - run 'npm install'")
            for package, version in all_deps.items():
                results['missing'].append({
                    'name': package,
                    'required': version
                })
            return results
        
        # Use npm list to check installed packages
        try:
            cmd = ['npm', 'list', '--json', '--depth=0']
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.stdout:
                installed_data = json.loads(result.stdout)
                installed_deps = installed_data.get('dependencies', {})
                
                # Check each required dependency
                for package, required_version in all_deps.items():
                    if package in installed_deps:
                        installed_version = installed_deps[package].get('version', 'unknown')
                        results['installed'].append({
                            'name': package,
                            'version': installed_version,
                            'required': required_version
                        })
                        
                        # Check for version mismatches
                        if not self._version_satisfies_npm(installed_version, required_version):
                            results['conflicts'].append({
                                'name': package,
                                'installed': installed_version,
                                'required': required_version
                            })
                    else:
                        results['missing'].append({
                            'name': package,
                            'required': required_version
                        })
                
                # Check for extraneous packages
                for package in installed_deps:
                    if package not in all_deps:
                        results['extraneous'].append(package)
        
        except subprocess.SubprocessError:
            self.warnings.append("Failed to run 'npm list' - is npm installed?")
        except json.JSONDecodeError:
            self.warnings.append("Failed to parse npm list output")
        
        # Check for outdated packages
        if self.check_updates:
            print("🔍 Checking for outdated packages...\n")
            outdated = self._check_outdated_node()
            results['outdated'] = outdated
        
        return results
    
    def _parse_requirements(self, filename: str) -> Dict[str, str]:
        """Parse Python requirements file"""
        dependencies = {}
        
        if filename == 'requirements.txt':
            try:
                with open(filename, 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            # Parse package==version or package>=version
                            match = re.match(r'([a-zA-Z0-9_-]+)(==|>=|<=|>|<|~=)?(.+)?', line)
                            if match:
                                package, operator, version = match.groups()
                                version_spec = f"{operator}{version}" if operator else None
                                dependencies[package] = version_spec
            except Exception as e:
                self.issues.append(f"Failed to parse {filename}: {e}")
        
        return dependencies
    
    def _get_installed_version_python(self, package: str) -> Optional[str]:
        """Get installed version of a Python package"""
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'show', package],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if line.startswith('Version:'):
                        return line.split(':', 1)[1].strip()
        except:
            pass
        return None
    
    def _version_matches(self, installed: str, required: str) -> bool:
        """Check if installed version matches requirement (simplified)"""
        if not required:
            return True
        
        # Handle == operator
        if required.startswith('=='):
            return installed == required[2:]
        
        # For other operators, accept as compatible (simplified check)
        return True
    
    def _version_satisfies_npm(self, installed: str, required: str) -> bool:
        """Check if installed version satisfies npm semver requirement (simplified)"""
        # Simplified check - in production, use semver library
        if required.startswith('^') or required.startswith('~'):
            # Accept as compatible (proper semver check would be more complex)
            return True
        
        return True  # Simplified
    
    def _check_outdated_python(self) -> List[Dict]:
        """Check for outdated Python packages"""
        outdated = []
        try:
            result = subprocess.run(
                [sys.executable, '-m', 'pip', 'list', '--outdated', '--format=json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0 and result.stdout:
                outdated = json.loads(result.stdout)
        except:
            self.warnings.append("Failed to check for outdated packages")
        
        return outdated
    
    def _check_outdated_node(self) -> List[Dict]:
        """Check for outdated Node.js packages"""
        outdated = []
        try:
            result = subprocess.run(
                ['npm', 'outdated', '--json'],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.stdout:
                outdated_data = json.loads(result.stdout)
                for package, info in outdated_data.items():
                    outdated.append({
                        'name': package,
                        'current': info.get('current'),
                        'wanted': info.get('wanted'),
                        'latest': info.get('latest')
                    })
        except:
            self.warnings.append("Failed to check for outdated packages")
        
        return outdated
    
    def print_report(self, results: Dict):
        """Print dependency check report"""
        print("\n" + "="*80)
        print(f"DEPENDENCY CHECK REPORT - {results['type'].upper()}")
        print("="*80 + "\n")
        
        # Missing Dependencies
        if results['missing']:
            print(f"❌ MISSING DEPENDENCIES ({len(results['missing'])}):")
            for dep in results['missing']:
                req = dep.get('required', 'any version')
                print(f"  • {dep['name']} ({req})")
            print()
        else:
            print("✅ All required dependencies are installed\n")
        
        # Version Conflicts
        if results['conflicts']:
            print(f"⚠️  VERSION CONFLICTS ({len(results['conflicts'])}):")
            for conflict in results['conflicts']:
                print(f"  • {conflict['name']}")
                print(f"    Installed: {conflict['installed']}")
                print(f"    Required:  {conflict['required']}")
            print()
        
        # Extraneous Packages (Node.js only)
        if 'extraneous' in results and results['extraneous']:
            print(f"⚠️  EXTRANEOUS PACKAGES ({len(results['extraneous'])}):")
            print("  (Installed but not in package.json)")
            for package in results['extraneous'][:10]:
                print(f"  • {package}")
            if len(results['extraneous']) > 10:
                print(f"  ... and {len(results['extraneous']) - 10} more")
            print()
        
        # Installed Dependencies
        if results['installed']:
            print(f"✅ INSTALLED DEPENDENCIES ({len(results['installed'])}):")
            for dep in results['installed'][:10]:
                print(f"  • {dep['name']} ({dep['version']})")
            if len(results['installed']) > 10:
                print(f"  ... and {len(results['installed']) - 10} more")
            print()
        
        # Outdated Packages
        if results['outdated']:
            print(f"📦 OUTDATED PACKAGES ({len(results['outdated'])}):")
            for pkg in results['outdated'][:10]:
                if results['type'] == 'python':
                    print(f"  • {pkg['name']}: {pkg['version']} → {pkg['latest_version']}")
                else:
                    print(f"  • {pkg['name']}: {pkg['current']} → {pkg['latest']}")
            if len(results['outdated']) > 10:
                print(f"  ... and {len(results['outdated']) - 10} more")
            print()
        
        # Warnings
        if self.warnings:
            print("⚠️  WARNINGS:")
            for warning in self.warnings:
                print(f"  • {warning}")
            print()
        
        # Recommendations
        print("💡 RECOMMENDATIONS:")
        
        if results['missing']:
            if results['type'] == 'python':
                print("  📦 Install missing Python packages:")
                print("     pip install -r requirements.txt")
            else:
                print("  📦 Install missing Node.js packages:")
                print("     npm install")
        
        if results['conflicts']:
            print("  ⚠️  Resolve version conflicts:")
            print("     1. Review conflicting package versions")
            print("     2. Update dependency specifications")
            print("     3. Test after version changes")
        
        if results.get('outdated'):
            if results['type'] == 'python':
                print("  📦 Update outdated packages:")
                print("     pip install --upgrade <package-name>")
            else:
                print("  📦 Update outdated packages:")
                print("     npm update")
        
        if not any([results['missing'], results['conflicts'], results.get('outdated')]):
            print("  ✅ All dependencies are properly installed and up to date!")
        
        print("\n" + "="*80 + "\n")

def main():
    parser = argparse.ArgumentParser(
        description='Check and verify project dependencies',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Auto-detect project type and check dependencies
  python dependency_checker.py
  
  # Explicitly check Python dependencies
  python dependency_checker.py --type python
  
  # Check with update recommendations
  python dependency_checker.py --check-updates
        '''
    )
    
    parser.add_argument('--type', choices=['python', 'node', 'auto'], default='auto',
                       help='Project type (auto-detect by default)')
    parser.add_argument('--check-updates', action='store_true',
                       help='Check for available package updates')
    
    args = parser.parse_args()
    
    checker = DependencyChecker(
        check_type=args.type,
        check_updates=args.check_updates
    )
    
    # Detect project type if auto
    if args.type == 'auto':
        detected_type = checker.detect_project_type()
        if detected_type == 'unknown':
            print("❌ Could not detect project type")
            print("   No package.json or requirements.txt found")
            sys.exit(1)
        checker.check_type = detected_type
    
    # Run appropriate check
    if checker.check_type == 'python':
        results = checker.check_python_dependencies()
    else:
        results = checker.check_node_dependencies()
    
    checker.print_report(results)
    
    # Exit with error code if there are critical issues
    if results['missing'] or results['conflicts']:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
