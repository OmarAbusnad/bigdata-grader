from pathlib import Path

from grader.discovery import discover_execution_plan
from grader.interactive_detection import infer_ingest_stdin


def _repo(tmp_path, source):
    (tmp_path / "src").mkdir(exist_ok=True)
    (tmp_path / "src" / "main.py").write_text(source, encoding="utf-8")
    return tmp_path


def test_direct_interactive_file_prompt(tmp_path):
    repo = _repo(tmp_path, '''
def main():
    target_file = input("أدخل المسار الكامل لملف البيانات:")
    print(target_file)
if __name__ == "__main__":
    main()
''')
    assert infer_ingest_stdin(repo/"src/main.py") == "{file}\\n".replace("\\n", "\n")
    plan = discover_execution_plan(repo)
    assert plan.ingest_command == "python src/main.py"
    assert plan.ingest_stdin == "{file}\n"


def test_verified_pipeline_menu_and_exit(tmp_path):
    repo = _repo(tmp_path, '''
def main():
    while True:
        print("1. Run API")
        print("2. ingest data (Data Pipeline)")
        print("3. Exet from program")
        choice = input("أدخل رقم الخيار:")
        if choice == "1":
            pass
        elif choice == "2":
            target_file = input("أدخل المسار الكامل لملف البيانات:")
            print(target_file)
            input("اضغط Enter للعودة للقائمة")
        elif choice == "3":
            break
if __name__ == "__main__":
    main()
''')
    plan = discover_execution_plan(repo)
    assert plan.ingest_command == "python src/main.py"
    assert plan.ingest_stdin == "2\n{file}\n\n3\n"


def test_no_menu_inference_without_proven_ingest_choice(tmp_path):
    repo = _repo(tmp_path, '''
def main():
    while True:
        print("2. delete database")
        print("3. exit")
        choice = input("Select:")
        if choice == "2":
            target_file = input("File:")
if __name__ == "__main__":
    main()
''')
    assert infer_ingest_stdin(repo/"src/main.py") is None


def test_multiple_file_prompts_not_guessed(tmp_path):
    repo = _repo(tmp_path, '''
def main():
    source_file = input("File:")
    another_path = input("Path:")
''')
    assert infer_ingest_stdin(repo/"src/main.py") is None
