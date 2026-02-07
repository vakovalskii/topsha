#!/usr/bin/env python3
"""
Agent Test Runner
Запускает тестовые сценарии и собирает результаты
"""

import json
import subprocess
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional
import sys

# Цвета для вывода
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


def load_scenarios(path: str) -> dict:
    """Загрузить сценарии из JSON"""
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def call_agent(prompt: str, user_id: int = 809532582, timeout: int = 120, source: str = "bot") -> dict:
    """Отправить запрос агенту через docker exec"""
    payload = json.dumps({
        "user_id": user_id,
        "chat_id": user_id,
        "message": prompt,
        "username": "test_runner",
        "chat_type": "private",
        "source": source
    })
    
    cmd = [
        "docker", "exec", "core",
        "curl", "-s", "-X", "POST",
        "http://localhost:4000/api/chat",
        "-H", "Content-Type: application/json",
        "-d", payload
    ]
    
    start_time = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        elapsed = time.time() - start_time
        
        if result.returncode != 0:
            return {
                "success": False,
                "error": f"curl failed: {result.stderr}",
                "elapsed": elapsed
            }
        
        try:
            response = json.loads(result.stdout)
            return {
                "success": True,
                "response": response.get("response", ""),
                "elapsed": elapsed
            }
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON decode error: {e}",
                "raw": result.stdout[:500],
                "elapsed": elapsed
            }
            
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Timeout after {timeout}s",
            "elapsed": timeout
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "elapsed": time.time() - start_time
        }


def clear_session(user_id: int = 809532582):
    """Очистить сессию агента"""
    payload = json.dumps({
        "user_id": user_id,
        "chat_id": user_id
    })
    
    cmd = [
        "docker", "exec", "core",
        "curl", "-s", "-X", "POST",
        "http://localhost:4000/api/clear",
        "-H", "Content-Type: application/json",
        "-d", payload
    ]
    
    subprocess.run(cmd, capture_output=True, timeout=10)


def run_tests(
    scenarios_path: str,
    categories: Optional[list] = None,
    ids: Optional[list] = None,
    difficulty: Optional[str] = None,
    limit: Optional[int] = None,
    delay: float = 2.0,
    clear_between: bool = True,
    verbose: bool = False,
    source_filter: Optional[str] = None,
    skip_userbot: bool = False
) -> dict:
    """Запустить тесты и собрать результаты"""
    
    data = load_scenarios(scenarios_path)
    scenarios = data["test_scenarios"]
    
    # Фильтрация
    if categories:
        scenarios = [s for s in scenarios if s["category"] in categories]
    if ids:
        scenarios = [s for s in scenarios if s["id"] in ids]
    if difficulty:
        scenarios = [s for s in scenarios if s["difficulty"] == difficulty]
    if source_filter:
        scenarios = [s for s in scenarios if s.get("source", "bot") == source_filter]
    if skip_userbot:
        scenarios = [s for s in scenarios if s.get("source", "bot") != "userbot"]
    if limit:
        scenarios = scenarios[:limit]
    
    results = {
        "run_at": datetime.now().isoformat(),
        "total": len(scenarios),
        "passed": 0,
        "failed": 0,
        "errors": 0,
        "total_time": 0,
        "by_category": {},
        "by_difficulty": {},
        "tests": []
    }
    
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}🧪 Agent Test Runner{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"📋 Tests to run: {len(scenarios)}")
    print(f"⏱️  Delay between tests: {delay}s")
    print(f"🔄 Clear session: {clear_between}")
    print()
    
    for i, scenario in enumerate(scenarios, 1):
        test_id = scenario["id"]
        category = scenario["category"]
        prompt = scenario["prompt"]
        difficulty_level = scenario["difficulty"]
        test_source = scenario.get("source", "bot")
        note = scenario.get("note", "")
        
        # Инициализация счётчиков по категориям
        if category not in results["by_category"]:
            results["by_category"][category] = {"passed": 0, "failed": 0, "errors": 0}
        if difficulty_level not in results["by_difficulty"]:
            results["by_difficulty"][difficulty_level] = {"passed": 0, "failed": 0, "errors": 0}
        
        source_label = f" [{test_source}]" if test_source != "bot" else ""
        print(f"{Colors.BLUE}[{i}/{len(scenarios)}]{Colors.RESET} Test #{test_id} ({category}/{difficulty_level}){source_label}")
        print(f"  📝 {prompt[:60]}{'...' if len(prompt) > 60 else ''}")
        if note and verbose:
            print(f"  📌 {note}")
        
        # Очистка сессии перед тестом
        if clear_between:
            clear_session()
        
        # Запуск теста
        result = call_agent(prompt, source=test_source)
        results["total_time"] += result.get("elapsed", 0)
        
        test_result = {
            "id": test_id,
            "category": category,
            "difficulty": difficulty_level,
            "source": test_source,
            "prompt": prompt,
            "expected_tools": scenario.get("expected_tools", []),
            "elapsed": result.get("elapsed", 0),
            "success": result.get("success", False),
            "response": result.get("response", ""),
            "error": result.get("error", "")
        }
        
        if result.get("success") and result.get("response"):
            # Считаем успешным если есть ответ
            test_result["status"] = "passed"
            results["passed"] += 1
            results["by_category"][category]["passed"] += 1
            results["by_difficulty"][difficulty_level]["passed"] += 1
            print(f"  {Colors.GREEN}✅ PASSED{Colors.RESET} ({result['elapsed']:.1f}s)")
            if verbose:
                response = result.get("response", "")[:200]
                print(f"  📤 {response}{'...' if len(result.get('response', '')) > 200 else ''}")
        elif result.get("error"):
            test_result["status"] = "error"
            results["errors"] += 1
            results["by_category"][category]["errors"] += 1
            results["by_difficulty"][difficulty_level]["errors"] += 1
            print(f"  {Colors.RED}❌ ERROR{Colors.RESET}: {result['error'][:100]}")
        else:
            test_result["status"] = "failed"
            results["failed"] += 1
            results["by_category"][category]["failed"] += 1
            results["by_difficulty"][difficulty_level]["failed"] += 1
            print(f"  {Colors.YELLOW}⚠️ FAILED{Colors.RESET}: Empty response")
        
        results["tests"].append(test_result)
        
        # Пауза между тестами
        if i < len(scenarios):
            time.sleep(delay)
    
    # Итоги
    print(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
    print(f"{Colors.CYAN}📊 Results Summary{Colors.RESET}")
    print(f"{Colors.BOLD}{'='*60}{Colors.RESET}")
    
    pass_rate = (results["passed"] / results["total"] * 100) if results["total"] > 0 else 0
    
    print(f"\n{Colors.GREEN}✅ Passed:{Colors.RESET} {results['passed']}")
    print(f"{Colors.YELLOW}⚠️ Failed:{Colors.RESET} {results['failed']}")
    print(f"{Colors.RED}❌ Errors:{Colors.RESET} {results['errors']}")
    print(f"\n📈 Pass rate: {pass_rate:.1f}%")
    print(f"⏱️  Total time: {results['total_time']:.1f}s")
    print(f"⏱️  Avg time: {results['total_time']/results['total']:.1f}s per test")
    
    print(f"\n{Colors.BOLD}By Category:{Colors.RESET}")
    for cat, stats in sorted(results["by_category"].items()):
        total = stats["passed"] + stats["failed"] + stats["errors"]
        rate = (stats["passed"] / total * 100) if total > 0 else 0
        print(f"  {cat}: {stats['passed']}/{total} ({rate:.0f}%)")
    
    print(f"\n{Colors.BOLD}By Difficulty:{Colors.RESET}")
    for diff, stats in sorted(results["by_difficulty"].items()):
        total = stats["passed"] + stats["failed"] + stats["errors"]
        rate = (stats["passed"] / total * 100) if total > 0 else 0
        print(f"  {diff}: {stats['passed']}/{total} ({rate:.0f}%)")
    
    return results


def save_results(results: dict, output_path: str):
    """Сохранить результаты в JSON"""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"\n💾 Results saved to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Agent Test Runner")
    parser.add_argument(
        "--scenarios", "-s",
        default="/home/ubuntu/LocalTopSH/test_scenarios.json",
        help="Path to scenarios JSON file"
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output file for results (default: test_results_<timestamp>.json)"
    )
    parser.add_argument(
        "--category", "-c",
        action="append",
        help="Filter by category (can be used multiple times)"
    )
    parser.add_argument(
        "--id", "-i",
        type=int,
        action="append",
        help="Run specific test IDs (can be used multiple times)"
    )
    parser.add_argument(
        "--difficulty", "-d",
        choices=["easy", "medium", "hard"],
        help="Filter by difficulty"
    )
    parser.add_argument(
        "--limit", "-l",
        type=int,
        help="Limit number of tests"
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=2.0,
        help="Delay between tests in seconds (default: 2.0)"
    )
    parser.add_argument(
        "--no-clear",
        action="store_true",
        help="Don't clear session between tests"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full responses"
    )
    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="List available categories and exit"
    )
    parser.add_argument(
        "--source",
        choices=["bot", "userbot"],
        help="Filter by source (bot or userbot)"
    )
    parser.add_argument(
        "--skip-userbot",
        action="store_true",
        help="Skip tests that require userbot"
    )
    
    args = parser.parse_args()
    
    # Список категорий
    if args.list_categories:
        data = load_scenarios(args.scenarios)
        print("\nAvailable categories:")
        for cat, desc in data["categories"].items():
            count = data["statistics"]["by_category"].get(cat, 0)
            print(f"  {cat} ({count}): {desc}")
        return
    
    # Запуск тестов
    results = run_tests(
        scenarios_path=args.scenarios,
        categories=args.category,
        ids=args.id,
        difficulty=args.difficulty,
        limit=args.limit,
        delay=args.delay,
        clear_between=not args.no_clear,
        verbose=args.verbose,
        source_filter=args.source,
        skip_userbot=args.skip_userbot
    )
    
    # Сохранение результатов
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"/home/ubuntu/LocalTopSH/test_results_{timestamp}.json"
    
    save_results(results, output_path)


if __name__ == "__main__":
    main()
