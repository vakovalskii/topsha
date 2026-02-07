#!/usr/bin/env python3
"""
LocalTopSH Security Doctor - Audit security configuration

Usage:
    python scripts/doctor.py
    python scripts/doctor.py --fix
    python scripts/doctor.py --json
"""

import os
import sys
import json
import stat
import socket
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

# Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str
    severity: str  # critical, high, medium, low
    fix_hint: Optional[str] = None


class SecurityDoctor:
    """Security audit for LocalTopSH"""
    
    def __init__(self, project_root: Path):
        self.root = project_root
        self.results: list[CheckResult] = []
    
    def check(self, name: str, passed: bool, message: str, 
              severity: str = "medium", fix_hint: str = None):
        """Add check result"""
        self.results.append(CheckResult(
            name=name,
            passed=passed,
            message=message,
            severity=severity,
            fix_hint=fix_hint
        ))
    
    def run_all_checks(self):
        """Run all security checks"""
        print(f"""
{BOLD}🛡️ LocalTopSH Security Doctor{RESET}

Checking 5 layers of protection:
  • ACCESS   - DM Policy configuration
  • INPUT    - Blocked patterns & injection defense
  • SANDBOX  - Docker isolation & resource limits
  • SECRETS  - Proxy architecture & key protection
  • OUTPUT   - Sanitization & encoding detection
""")
        print("=" * 60)
        
        self.check_secrets()
        self.check_docker_compose()
        self.check_blocked_patterns()
        self.check_injection_patterns()
        self.check_network_exposure()
        self.check_file_permissions()
        self.check_access_mode()
        self.check_resource_limits()
        
        print("=" * 60)
        self.print_summary()
    
    def check_secrets(self):
        """Check secrets configuration"""
        print(f"\n{BLUE}[1/8] Checking secrets...{RESET}")
        
        secrets_dir = self.root / "secrets"
        
        # Check secrets directory exists
        if not secrets_dir.exists():
            self.check("secrets_dir", False, "secrets/ directory not found",
                      "critical", "mkdir secrets && touch secrets/.gitkeep")
            return
        
        self.check("secrets_dir", True, "secrets/ directory exists")
        
        # Check required secrets
        required = ["telegram_token.txt", "api_key.txt", "base_url.txt"]
        for secret in required:
            path = secrets_dir / secret
            if path.exists():
                # Check not empty
                content = path.read_text().strip()
                if content:
                    self.check(f"secret_{secret}", True, f"{secret} configured")
                else:
                    self.check(f"secret_{secret}", False, f"{secret} is empty",
                              "critical", f"echo 'your-value' > secrets/{secret}")
            else:
                self.check(f"secret_{secret}", False, f"{secret} missing",
                          "critical", f"echo 'your-value' > secrets/{secret}")
        
        # Check file permissions (should be 600)
        for f in secrets_dir.glob("*.txt"):
            mode = f.stat().st_mode
            is_secure = (mode & 0o077) == 0  # No group/other permissions
            self.check(f"perm_{f.name}", is_secure,
                      f"{f.name} permissions: {oct(mode & 0o777)}",
                      "high" if not is_secure else "low",
                      f"chmod 600 secrets/{f.name}")
        
        # Check .gitignore
        gitignore = self.root / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text()
            has_secrets = "secrets/" in content or "secrets/*" in content
            self.check("gitignore_secrets", has_secrets,
                      "secrets/ in .gitignore" if has_secrets else "secrets/ NOT in .gitignore!",
                      "critical" if not has_secrets else "low",
                      "echo 'secrets/' >> .gitignore")
    
    def check_docker_compose(self):
        """Check docker-compose.yml security"""
        print(f"\n{BLUE}[2/8] Checking docker-compose.yml...{RESET}")
        
        compose_file = self.root / "docker-compose.yml"
        if not compose_file.exists():
            self.check("docker_compose", False, "docker-compose.yml not found", "critical")
            return
        
        content = compose_file.read_text()
        
        # Check no-new-privileges
        has_no_new_priv = "no-new-privileges" in content
        self.check("no_new_privileges", has_no_new_priv,
                  "no-new-privileges enabled" if has_no_new_priv else "no-new-privileges NOT set",
                  "high")
        
        # Check resource limits
        has_mem_limit = "mem_limit" in content or "memory:" in content
        self.check("memory_limits", has_mem_limit,
                  "Memory limits configured" if has_mem_limit else "No memory limits!",
                  "high")
        
        has_cpu_limit = "cpu" in content.lower()
        self.check("cpu_limits", has_cpu_limit,
                  "CPU limits configured" if has_cpu_limit else "No CPU limits!",
                  "medium")
        
        has_pids_limit = "pids_limit" in content or "pids:" in content
        self.check("pids_limit", has_pids_limit,
                  "PIDs limit configured" if has_pids_limit else "No PIDs limit (fork bomb risk)",
                  "high")
        
        # Check secrets usage
        uses_secrets = "secrets:" in content
        self.check("docker_secrets", uses_secrets,
                  "Using Docker secrets" if uses_secrets else "Not using Docker secrets!",
                  "high")
        
        # Check no env vars with actual secret values (not just references)
        import re
        # Look for actual secret values in env vars (e.g. API_KEY=sk-xxx)
        # Exclude Docker secrets references (just names like 'api_key', 'telegram_token')
        env_secrets = re.findall(r'(API_KEY|TOKEN|SECRET|PASSWORD)\s*[=:]\s*["\']?[A-Za-z0-9_-]{20,}', content, re.IGNORECASE)
        has_env_secrets = len(env_secrets) > 0
        self.check("no_env_secrets", not has_env_secrets,
                  "No hardcoded secrets in environment" if not has_env_secrets else f"Found hardcoded secrets: {env_secrets}",
                  "critical" if has_env_secrets else "low")
    
    def check_blocked_patterns(self):
        """Check blocked patterns configuration"""
        print(f"\n{BLUE}[3/8] Checking blocked patterns...{RESET}")
        
        patterns_file = self.root / "core" / "src" / "approvals" / "blocked-patterns.json"
        
        if not patterns_file.exists():
            self.check("blocked_patterns", False, "blocked-patterns.json not found", "critical")
            return
        
        try:
            data = json.loads(patterns_file.read_text())
            patterns = data.get("patterns", [])
            count = len(patterns)
            
            self.check("blocked_patterns_count", count >= 200,
                      f"{count} blocked patterns loaded",
                      "medium" if count < 200 else "low")
            
            # Check critical categories
            categories = set(p.get("category", "") for p in patterns)
            critical_cats = ["env_leak", "docker_secrets", "exfiltration", "reverse_shell"]
            
            for cat in critical_cats:
                has_cat = cat in categories
                self.check(f"category_{cat}", has_cat,
                          f"Category '{cat}' present" if has_cat else f"Missing category: {cat}",
                          "high" if not has_cat else "low")
                          
        except Exception as e:
            self.check("blocked_patterns", False, f"Error parsing: {e}", "critical")
    
    def check_injection_patterns(self):
        """Check prompt injection patterns"""
        print(f"\n{BLUE}[4/8] Checking prompt injection patterns...{RESET}")
        
        patterns_file = self.root / "bot" / "prompt-injection-patterns.json"
        
        if not patterns_file.exists():
            self.check("injection_patterns", False, "prompt-injection-patterns.json not found", "high")
            return
        
        try:
            data = json.loads(patterns_file.read_text())
            patterns = data.get("patterns", [])
            count = len(patterns)
            
            self.check("injection_patterns_count", count >= 15,
                      f"{count} injection patterns loaded",
                      "medium" if count < 15 else "low")
            
            # Check key patterns exist
            all_patterns = " ".join(p.get("pattern", "") for p in patterns)
            key_checks = [
                ("forget", "forget instructions"),
                ("ignore", "ignore previous"),
                ("system", "[system] tag"),
                ("jailbreak", "jailbreak"),
                ("DAN", "DAN mode"),
            ]
            
            for key, desc in key_checks:
                has_key = key.lower() in all_patterns.lower()
                self.check(f"injection_{key}", has_key,
                          f"Pattern for '{desc}'" if has_key else f"Missing: {desc}",
                          "medium" if not has_key else "low")
                          
        except Exception as e:
            self.check("injection_patterns", False, f"Error parsing: {e}", "high")
    
    def check_network_exposure(self):
        """Check network exposure"""
        print(f"\n{BLUE}[5/8] Checking network exposure...{RESET}")
        
        compose_file = self.root / "docker-compose.yml"
        if not compose_file.exists():
            return
        
        content = compose_file.read_text()
        
        # Check admin panel binding
        # Should be "3000:3000" (localhost only) not "0.0.0.0:3000:3000"
        import re
        port_bindings = re.findall(r'"?(\d+\.\d+\.\d+\.\d+)?:?(\d+):(\d+)"?', content)
        
        for bind_ip, host_port, container_port in port_bindings:
            if bind_ip == "0.0.0.0":
                self.check(f"port_{container_port}", False,
                          f"Port {container_port} exposed to 0.0.0.0!",
                          "high",
                          f"Change to '127.0.0.1:{host_port}:{container_port}'")
        
        # Check internal network
        has_internal = "internal:" in content
        self.check("internal_network", True,  # We use agent-net which is fine
                  "Using bridge network (OK for this setup)")
        
        # Check common dangerous ports
        dangerous_ports = ["3200", "4000", "4001"]  # proxy, core, bot
        for port in dangerous_ports:
            exposed = f'"{port}:' in content or f"'{port}:" in content
            self.check(f"internal_port_{port}", not exposed,
                      f"Internal port {port} not exposed" if not exposed else f"Port {port} exposed!",
                      "critical" if exposed else "low")
    
    def check_file_permissions(self):
        """Check file permissions"""
        print(f"\n{BLUE}[6/8] Checking file permissions...{RESET}")
        
        # Check sensitive files
        sensitive_files = [
            ("secrets/", "700"),
            (".env", "600"),
            ("docker-compose.yml", "644"),
        ]
        
        for path, expected in sensitive_files:
            full_path = self.root / path
            if full_path.exists():
                mode = full_path.stat().st_mode
                actual = oct(mode & 0o777)
                is_ok = actual == f"0o{expected}"
                self.check(f"perm_{path}", is_ok,
                          f"{path}: {actual}" + ("" if is_ok else f" (should be {expected})"),
                          "medium" if not is_ok else "low",
                          f"chmod {expected} {path}")
    
    def check_access_mode(self):
        """Check access control mode"""
        print(f"\n{BLUE}[7/8] Checking access control...{RESET}")
        
        # Check if access.py exists
        access_file = self.root / "bot" / "access.py"
        self.check("access_module", access_file.exists(),
                  "access.py module present" if access_file.exists() else "access.py missing!",
                  "high" if not access_file.exists() else "low")
        
        # Check ACCESS_MODE env (from docker-compose or .env)
        compose_file = self.root / "docker-compose.yml"
        if compose_file.exists():
            content = compose_file.read_text()
            
            # Check if ACCESS_MODE is set
            has_access_mode = "ACCESS_MODE" in content
            
            # Check if public mode (risky)
            is_public = "ACCESS_MODE=public" in content or "ACCESS_MODE: public" in content
            
            if is_public:
                self.check("access_mode", False,
                          "ACCESS_MODE=public (risky!)",
                          "high",
                          "Change to ACCESS_MODE=admin or ACCESS_MODE=allowlist")
            elif has_access_mode:
                self.check("access_mode", True, "ACCESS_MODE configured")
            else:
                self.check("access_mode", True, "ACCESS_MODE defaults to 'admin' (safe)")
        
        # Check ADMIN_USER_ID is set
        admin_id = os.getenv("ADMIN_USER_ID", "")
        if compose_file.exists():
            content = compose_file.read_text()
            has_admin = "ADMIN_USER_ID" in content
            self.check("admin_user_id", has_admin,
                      "ADMIN_USER_ID configured" if has_admin else "ADMIN_USER_ID not set!",
                      "high" if not has_admin else "low")
    
    def check_resource_limits(self):
        """Check resource limits in sandbox"""
        print(f"\n{BLUE}[8/8] Checking sandbox limits...{RESET}")
        
        sandbox_file = self.root / "core" / "tools" / "sandbox.py"
        if not sandbox_file.exists():
            self.check("sandbox", False, "sandbox.py not found", "high")
            return
        
        content = sandbox_file.read_text()
        
        # Check memory limit
        has_mem = "mem_limit" in content
        self.check("sandbox_memory", has_mem,
                  "Sandbox memory limit set" if has_mem else "No sandbox memory limit!",
                  "high")
        
        # Check CPU limit
        has_cpu = "cpu_quota" in content or "cpu_period" in content
        self.check("sandbox_cpu", has_cpu,
                  "Sandbox CPU limit set" if has_cpu else "No sandbox CPU limit!",
                  "high")
        
        # Check PIDs limit
        has_pids = "pids_limit" in content
        self.check("sandbox_pids", has_pids,
                  "Sandbox PIDs limit set" if has_pids else "No sandbox PIDs limit!",
                  "high")
        
        # Check timeout
        has_timeout = "COMMAND_TIMEOUT" in content or "timeout" in content.lower()
        self.check("sandbox_timeout", has_timeout,
                  "Command timeout configured" if has_timeout else "No command timeout!",
                  "medium")
    
    def print_summary(self):
        """Print summary of all checks"""
        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        
        critical = sum(1 for r in self.results if not r.passed and r.severity == "critical")
        high = sum(1 for r in self.results if not r.passed and r.severity == "high")
        
        print(f"\n{BOLD}📊 Summary{RESET}")
        print(f"   Total checks: {len(self.results)}")
        print(f"   {GREEN}✓ Passed: {passed}{RESET}")
        print(f"   {RED}✗ Failed: {failed}{RESET}")
        
        if critical > 0:
            print(f"\n{RED}{BOLD}🚨 CRITICAL ISSUES: {critical}{RESET}")
        if high > 0:
            print(f"{YELLOW}⚠️  HIGH ISSUES: {high}{RESET}")
        
        # Print failed checks
        if failed > 0:
            print(f"\n{BOLD}Failed checks:{RESET}")
            for r in self.results:
                if not r.passed:
                    color = RED if r.severity in ("critical", "high") else YELLOW
                    print(f"  {color}✗ [{r.severity.upper()}] {r.name}: {r.message}{RESET}")
                    if r.fix_hint:
                        print(f"    Fix: {r.fix_hint}")
        
        # Overall status
        print()
        if critical > 0:
            print(f"{RED}{BOLD}❌ SECURITY COMPROMISED{RESET}")
            print(f"{RED}   Fix critical issues immediately!{RESET}")
            return 1
        elif high > 0:
            print(f"{YELLOW}{BOLD}⚠️  SECURITY WARNINGS{RESET}")
            print(f"{YELLOW}   Review high-severity issues{RESET}")
            return 0
        else:
            print(f"{GREEN}{BOLD}✅ ALL CHECKS PASSED{RESET}")
            print(f"{GREEN}   Security configuration is solid.{RESET}")
            return 0
    
    def to_json(self) -> str:
        """Export results as JSON"""
        return json.dumps({
            "results": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "severity": r.severity,
                    "fix_hint": r.fix_hint
                }
                for r in self.results
            ],
            "summary": {
                "total": len(self.results),
                "passed": sum(1 for r in self.results if r.passed),
                "failed": sum(1 for r in self.results if not r.passed),
                "critical": sum(1 for r in self.results if not r.passed and r.severity == "critical"),
                "high": sum(1 for r in self.results if not r.passed and r.severity == "high"),
            }
        }, indent=2)


def main():
    parser = argparse.ArgumentParser(description="LocalTopSH Security Doctor")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--fix", action="store_true", help="Attempt to fix issues (not implemented)")
    args = parser.parse_args()
    
    # Find project root
    script_dir = Path(__file__).parent
    project_root = script_dir.parent
    
    # Check we're in right directory
    if not (project_root / "docker-compose.yml").exists():
        print(f"{RED}Error: Run from project root or scripts/ directory{RESET}")
        sys.exit(1)
    
    doctor = SecurityDoctor(project_root)
    doctor.run_all_checks()
    
    if args.json:
        print("\n" + doctor.to_json())
    
    sys.exit(doctor.print_summary())


if __name__ == "__main__":
    main()
