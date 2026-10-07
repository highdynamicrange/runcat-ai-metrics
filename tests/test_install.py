import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('installer', Path(__file__).parents[1] / 'install.py')
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)

class InstallTests(unittest.TestCase):
    def test_reinstall_and_uninstall_preserve_other_hooks(self):
        script = Path('/tmp/example/runcat-hook.py')
        other = {'type': 'command', 'command': 'other-hook', 'timeout': 5}
        data = {'hooks': {'Stop': [{'hooks': [other]}], 'SessionStart': []}}
        installer.merge_hook(data, script)
        installer.merge_hook(data, script)
        self.assertEqual(len(data['hooks']['Stop']), 2)
        installer.merge_hook(data, script, True)
        self.assertEqual(data, {'hooks': {'Stop': [{'hooks': [other]}], 'SessionStart': []}})

if __name__ == '__main__':
    unittest.main()
