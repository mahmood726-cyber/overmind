import subprocess
import sys
prompt = sys.stdin.buffer.read().decode('utf-8', errors='replace').splitlines()
primary = None
for index, line in enumerate(prompt):
    if line.strip() == 'PRIMARY COMMAND:' and index + 1 < len(prompt):
        candidate = prompt[index + 1].strip()
        if candidate.startswith('- '):
            primary = candidate[2:]
            break
if not primary:
    print('COMMAND: none', flush=True)
    print('build failed', flush=True)
    sys.exit(1)
print(f'COMMAND: {primary}', flush=True)
result = subprocess.run(primary, shell=True, text=True, capture_output=True)
if result.stdout:
    print(result.stdout.rstrip(), flush=True)
if result.stderr:
    print(result.stderr.rstrip(), flush=True)
if result.returncode == 0:
    print('tests passed', flush=True)
else:
    print('tests failed', flush=True)
sys.exit(result.returncode)
