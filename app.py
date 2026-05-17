import importlib.util
import sys
from pathlib import Path


PACKAGE_DIR = Path(__file__).parent / "app"
spec = importlib.util.spec_from_file_location(
    "clean_app",
    PACKAGE_DIR / "__init__.py",
    submodule_search_locations=[str(PACKAGE_DIR)],
)
clean_app = importlib.util.module_from_spec(spec)
sys.modules["clean_app"] = clean_app
spec.loader.exec_module(clean_app)

app = clean_app.create_app()


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
