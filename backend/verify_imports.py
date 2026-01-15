
import sys
import os
import importlib
from pathlib import Path

# Add backend directory to sys.path
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(backend_dir)

print(f"Testing imports from: {backend_dir}")

modules_to_test = [
    "app.main",
    "app.core.llm_factory",
    "app.core.prompts",
    "app.db.database",
    "app.db.storage",
    "app.models",
    "app.services.task_service",
    "app.services.optimizer_service",
    "app.api.routers.auto_iterate",
    "app.api.routers.projects",
    "app.api.routers.tasks",
    "app.api.routers.playground",
    "app.api.routers.upload",
    "app.api.routers.knowledge_base",
    "app.api.routers.global_models",
    "app.api.routers.config",
    "app.engine.multi_strategy",
    "app.engine.llm_helper",
    "app.engine.diagnosis",
    "app.engine.knowledge_base",
    "app.engine.prompt_evaluator",
    "app.engine.candidate_generator",
    "app.engine.advanced_diagnosis",
    "app.engine.intent_analyzer",
    "app.engine.hard_case_detection",
    "app.engine.multi_intent_optimizer",
    "app.engine.strategy_matcher",
    "app.engine.validation",
    "scripts.migrate_to_sqlite"
]

failed_modules = []

for module_name in modules_to_test:
    try:
        print(f"Importing {module_name}...", end=" ")
        importlib.import_module(module_name)
        print("OK")
    except Exception as e:
        print(f"FAILED: {e}")
        failed_modules.append((module_name, str(e)))

print("\n" + "="*30)
if failed_modules:
    print(f"Found {len(failed_modules)} failed module imports:")
    for name, error in failed_modules:
        print(f" - {name}: {error}")
    sys.exit(1)
else:
    print("All modules imported successfully!")
    sys.exit(0)
