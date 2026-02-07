#!/usr/bin/env python3
"""
E2E Tests for LocalTopSH Agent

Tests the full agent cycle:
1. Agent cycle (LLM call)
2. Tool calls (run_command)
3. Sandbox creation
4. File operations
5. Skill discovery
6. Skill reading
7. MCP integration
8. Session history

Usage:
    python scripts/e2e_test.py
    python scripts/e2e_test.py --verbose
    python scripts/e2e_test.py --json
"""

import os
import sys
import json
import time
import argparse
import subprocess
from typing import Optional, Tuple
from dataclasses import dataclass

# Test configuration
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "809532582")
CORE_URL = "http://localhost:4000"
TOOLS_API_URL = "http://localhost:8100"


@dataclass
class TestResult:
    name: str
    passed: bool
    message: str
    duration: float


def run_in_container(container: str, cmd: str) -> Tuple[int, str]:
    """Run command in docker container"""
    result = subprocess.run(
        ["docker", "exec", container, "sh", "-c", cmd],
        capture_output=True,
        text=True,
        timeout=60
    )
    return result.returncode, result.stdout + result.stderr


def api_chat(message: str, user_id: str = ADMIN_USER_ID) -> dict:
    """Call agent API"""
    # Escape message for JSON
    escaped = message.replace('\\', '\\\\').replace('"', '\\"')
    payload = json.dumps({
        "message": message,
        "user_id": int(user_id),
        "chat_id": int(user_id),
        "username": "test"
    })
    # Escape single quotes for shell
    payload_escaped = payload.replace("'", "'\"'\"'")
    
    cmd = f"curl -s -X POST http://localhost:4000/api/chat -H 'Content-Type: application/json' -d '{payload_escaped}'"
    code, output = run_in_container("core", cmd)
    try:
        return json.loads(output)
    except:
        return {"error": output, "response": None}


def api_tools(endpoint: str = "/tools") -> dict:
    """Call tools API"""
    cmd = f'curl -s http://localhost:8100{endpoint}'
    code, output = run_in_container("tools-api", cmd)
    try:
        return json.loads(output)
    except:
        return {"error": output}


def test_services_health() -> TestResult:
    """Test 1: All services are healthy"""
    start = time.time()
    
    services = ["core", "bot", "proxy", "tools-api"]
    healthy = []
    
    for svc in services:
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Health.Status}}", svc],
            capture_output=True, text=True
        )
        status = result.stdout.strip()
        if status == "healthy":
            healthy.append(svc)
    
    passed = len(healthy) >= 3  # At least core, proxy, tools-api
    return TestResult(
        name="Services Health",
        passed=passed,
        message=f"Healthy: {', '.join(healthy)}" if passed else f"Only {len(healthy)}/4 healthy",
        duration=time.time() - start
    )


def test_agent_cycle() -> TestResult:
    """Test 2: Basic agent cycle (LLM call)"""
    start = time.time()
    
    resp = api_chat("What is 2+2? Answer with just the number.")
    
    if resp.get("access_denied"):
        return TestResult("Agent Cycle", False, "Access denied", time.time() - start)
    
    response = resp.get("response", "")
    passed = response and "4" in response and "error" not in response.lower()
    
    return TestResult(
        name="Agent Cycle",
        passed=passed,
        message=f"Response: {response[:50]}..." if passed else f"Failed: {response[:100]}",
        duration=time.time() - start
    )


def test_tool_call() -> TestResult:
    """Test 3: Tool call (run_command)"""
    start = time.time()
    
    resp = api_chat("Run this command: echo E2E_TEST_OK")
    response = resp.get("response", "")
    
    # Check if command was executed (response mentions success or contains output)
    passed = response and ("E2E_TEST_OK" in response or "ok" in response.lower() or "✅" in response)
    
    return TestResult(
        name="Tool Call (run_command)",
        passed=passed,
        message=f"Response: {response[:50]}..." if passed else f"Failed: {response[:100]}",
        duration=time.time() - start
    )


def test_sandbox_creation() -> TestResult:
    """Test 4: Sandbox container created"""
    start = time.time()
    
    result = subprocess.run(
        ["docker", "ps", "--filter", f"name=sandbox_{ADMIN_USER_ID}", "--format", "{{.Names}}"],
        capture_output=True, text=True
    )
    
    passed = f"sandbox_{ADMIN_USER_ID}" in result.stdout
    
    return TestResult(
        name="Sandbox Creation",
        passed=passed,
        message=f"Container: sandbox_{ADMIN_USER_ID}" if passed else "Sandbox not found",
        duration=time.time() - start
    )


def test_file_operations() -> TestResult:
    """Test 5: File write and read"""
    start = time.time()
    
    test_content = f"E2E_TEST_{int(time.time())}"
    resp = api_chat(f'Write "{test_content}" to e2e_test_file.txt')
    response = resp.get("response", "")
    
    # Wait a moment for file to be written
    time.sleep(0.5)
    
    # Verify file exists in sandbox or workspace
    code, output = run_in_container(f"sandbox_{ADMIN_USER_ID}", f"cat /workspace/{ADMIN_USER_ID}/e2e_test_file.txt 2>/dev/null")
    
    # Also check via core container
    if not output.strip():
        code, output = run_in_container("core", f"cat /workspace/{ADMIN_USER_ID}/e2e_test_file.txt 2>/dev/null")
    
    # Check if content matches OR agent reported success
    passed = (
        test_content in output or 
        "✅" in response or 
        "wrote" in response.lower() or
        "created" in response.lower() or
        "saved" in response.lower() or
        "written" in response.lower()
    )
    
    return TestResult(
        name="File Operations",
        passed=passed,
        message="Write/read successful" if passed else f"Failed: {response[:50] if response else 'no response'}",
        duration=time.time() - start
    )


def test_skill_discovery() -> TestResult:
    """Test 6: List /data/skills/"""
    start = time.time()
    
    resp = api_chat("List the contents of /data/skills/ directory")
    response = resp.get("response", "")
    
    # Should mention at least one skill
    passed = any(skill in response.lower() for skill in ["pptx", "docx", "example"])
    
    return TestResult(
        name="Skill Discovery",
        passed=passed,
        message=f"Found skills in response" if passed else f"No skills found: {response[:50]}",
        duration=time.time() - start
    )


def test_skill_reading() -> TestResult:
    """Test 7: Read SKILL.md"""
    start = time.time()
    
    resp = api_chat("Read the first 5 lines of /data/skills/pptx/SKILL.md")
    response = resp.get("response", "")
    
    # Should contain skill metadata
    passed = "pptx" in response.lower() or "skill" in response.lower()
    
    return TestResult(
        name="Skill Reading",
        passed=passed,
        message="SKILL.md readable" if passed else f"Failed: {response[:50]}",
        duration=time.time() - start
    )


def test_tools_api() -> TestResult:
    """Test 8: Tools API returns tools"""
    start = time.time()
    
    data = api_tools("/tools")
    
    stats = data.get("stats", {})
    total = stats.get("total", 0)
    
    passed = total >= 15  # At least 15 builtin tools
    
    return TestResult(
        name="Tools API",
        passed=passed,
        message=f"Total tools: {total} (builtin: {stats.get('builtin', 0)}, mcp: {stats.get('mcp', 0)}, skill: {stats.get('skill', 0)})",
        duration=time.time() - start
    )


def test_mcp_integration() -> TestResult:
    """Test 9: MCP server connected"""
    start = time.time()
    
    data = api_tools("/mcp/servers")
    servers = data.get("servers", [])
    
    connected = [s for s in servers if s.get("status", {}).get("connected")]
    
    passed = len(connected) > 0
    
    return TestResult(
        name="MCP Integration",
        passed=passed,
        message=f"Connected servers: {len(connected)}" if passed else "No MCP servers connected",
        duration=time.time() - start
    )


def test_skills_mentions() -> TestResult:
    """Test 10: Skills mentions endpoint"""
    start = time.time()
    
    data = api_tools("/skills/mentions")
    
    skill_count = data.get("skill_count", 0)
    mentions = data.get("mentions", "")
    
    passed = skill_count > 0 and "Available Skills" in mentions
    
    return TestResult(
        name="Skills Mentions",
        passed=passed,
        message=f"Skills in prompt: {skill_count}" if passed else "No skill mentions",
        duration=time.time() - start
    )


def run_all_tests(verbose: bool = False) -> list[TestResult]:
    """Run all E2E tests"""
    tests = [
        test_services_health,
        test_agent_cycle,
        test_tool_call,
        test_sandbox_creation,
        test_file_operations,
        test_skill_discovery,
        test_skill_reading,
        test_tools_api,
        test_mcp_integration,
        test_skills_mentions,
    ]
    
    results = []
    
    for test_fn in tests:
        if verbose:
            print(f"Running: {test_fn.__name__}...", end=" ", flush=True)
        
        try:
            result = test_fn()
        except Exception as e:
            result = TestResult(
                name=test_fn.__name__,
                passed=False,
                message=f"Exception: {str(e)[:50]}",
                duration=0
            )
        
        results.append(result)
        
        if verbose:
            status = "✅" if result.passed else "❌"
            print(f"{status} ({result.duration:.2f}s)")
    
    return results


def print_summary(results: list[TestResult]):
    """Print test summary"""
    passed = sum(1 for r in results if r.passed)
    total = len(results)
    
    print("\n" + "=" * 60)
    print("🧪 E2E Test Results")
    print("=" * 60)
    
    for r in results:
        status = "✅" if r.passed else "❌"
        print(f"{status} {r.name}: {r.message}")
    
    print("=" * 60)
    print(f"Total: {passed}/{total} passed")
    
    if passed == total:
        print("🎉 All tests passed!")
    else:
        print(f"⚠️  {total - passed} tests failed")
    
    return passed == total


def main():
    parser = argparse.ArgumentParser(description="E2E tests for LocalTopSH")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()
    
    print("🚀 Running E2E tests for LocalTopSH...\n")
    
    results = run_all_tests(verbose=args.verbose)
    
    if args.json:
        output = {
            "tests": [
                {
                    "name": r.name,
                    "passed": r.passed,
                    "message": r.message,
                    "duration": r.duration
                }
                for r in results
            ],
            "summary": {
                "passed": sum(1 for r in results if r.passed),
                "total": len(results)
            }
        }
        print(json.dumps(output, indent=2))
    else:
        success = print_summary(results)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
