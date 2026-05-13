import os

extensions = ('.py', '.js', '.html', '.css')
exclude_dirs = {'node_modules', '.git', '__pycache__', 'venv', 'env'}

with open('kazpatent_source.txt', 'w', encoding='utf-8') as out:
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for f in sorted(files):
            if f.endswith(extensions):
                path = os.path.join(root, f)
                out.write(f"\n{'='*60}\n")
                out.write(f"// Файл: {path}\n")
                out.write(f"{'='*60}\n\n")
                with open(path, 'r', encoding='utf-8', errors='ignore') as file:
                    out.write(file.read())
                out.write("\n")

print("Готово! Файл kazpatent_source.txt создан!")